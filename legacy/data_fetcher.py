import pandas as pd
from dhanhq import dhanhq
import logging
from datetime import datetime, timedelta
import config
import yfinance as yf
import os

class DhanFetcher:
    def __init__(self):
        self.client_id = config.DHAN_CLIENT_ID
        self.access_token = config.DHAN_ACCESS_TOKEN
        self.logger = logging.getLogger(__name__)
        self.security_map = None
        self.dhan = None
        
        # Initialize Dhan client
        try:
            # Check if secrets are default placeholders
            if self.client_id == "YOUR_CLIENT_ID":
                self.logger.warning("Dhan Credentials not set. API calls will fail.")
            else:
                self.dhan = dhanhq(self.client_id, self.access_token)
                # NOTE: The dhanhq library has been patched to use https://sandbox.dhan.co/v2
                self.load_security_list()
        except Exception as e:
            self.logger.error(f"Failed to init DhanHQ: {e}")

    def load_security_list(self):
        csv_file = "security_id_list.csv"
        # Download if not exists
        if not os.path.exists(csv_file):
            if self.dhan:
                self.logger.info("Downloading Security List...")
                try:
                    self.dhan.fetch_security_list(mode='compact', filename=csv_file)
                except Exception as e:
                    self.logger.error(f"Failed to download security list: {e}")
                    return

        if os.path.exists(csv_file):
            try:
                # Load CSV
                self.security_map = pd.read_csv(csv_file)
                self.logger.info(f"Loaded {len(self.security_map)} securities.")
            except Exception as e:
                self.logger.error(f"Error loading security list CSV: {e}")

    def get_security_details(self, symbol):
        if self.security_map is None:
            return None
        
        # Filter for symbol (Exact match on SEM_TRADING_SYMBOL)
        res = self.security_map[self.security_map['SEM_TRADING_SYMBOL'] == symbol]
        
        if res.empty:
            # Try appending '-EQ' or similar if not found?
            return None
        
        # Prefer Equity (NSE) or Index
        # We try to pick the one with 'NSE' in exchange segment usually
        # The compact list columns: SEM_EXM_EXCH_ID, SEM_SEGMENT, SEM_SMST_SECURITY_ID...
        # 'SEM_EXM_SEG_ID' was incorrect guess. It seems 'SEM_EXM_EXCH_ID' is the exchange?
        
        # known: NSE, BSE.
        if len(res) > 1:
            nse_match = res[res['SEM_EXM_EXCH_ID'] == 'NSE']
            if not nse_match.empty:
                return nse_match.iloc[0]
                
        return res.iloc[0]

    def fetch_ohlc(self, symbol, timeframe, days=5, start_date=None, end_date=None):
        """
        Fetches historical OHLC data from Dhan API.
        """
        # Fallback if no client
        if self.dhan is None:
            self.logger.info("Dhan client unavailable. Using YFinance.")
            return self.fetch_yfinance_data(symbol, timeframe, days, start_date, end_date)

        # Get Security ID
        row = self.get_security_details(symbol)
        if row is None:
            self.logger.error(f"Symbol {symbol} not found in Security List. Using YFinance.")
            return self.fetch_yfinance_data(symbol, timeframe, days, start_date, end_date)
        
        security_id = str(row['SEM_SMST_SECURITY_ID'])
        
        # Map Exchange Segment explicitly
        exch_id = row['SEM_EXM_EXCH_ID']
        if exch_id == 'NSE':
            exchange_segment = self.dhan.NSE
        elif exch_id == 'BSE':
            exchange_segment = self.dhan.BSE
        else:
            exchange_segment = exch_id # Try raw
            
        instrument_type = row['SEM_INSTRUMENT_NAME']
        
        # Date handling
        if start_date and end_date:
            from_d = start_date
            to_d = end_date
        else:
            to_d = datetime.now().strftime('%Y-%m-%d')
            from_d = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        try:
            # API Call
            res = self.dhan.intraday_minute_data(
                security_id=security_id,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                from_date=from_d,
                to_date=to_d,
                interval=int(timeframe)
            )
            
            if res.get('status') == 'failure':
                # If failure (e.g. Data not available), log and fallback
                self.logger.warning(f"Dhan API Failure for {symbol}: {res.get('remarks', 'Unknown error')}")
                return self.fetch_yfinance_data(symbol, timeframe, days, start_date, end_date)
                
            data = res.get('data')
            if not data:
                self.logger.warning(f"No data returned for {symbol}")
                return self.fetch_yfinance_data(symbol, timeframe, days, start_date, end_date)

            # Parse Response
            # Response: {'status': 'success', 'data': {'start_Time': [...], 'open': [...], ...}}
            df = pd.DataFrame(data)
            
            # Convert Dhan Time to Datetime
            # Dhan time format logic (Dhan uses 'start_Time' usually)
            
            time_col = None
            if 'start_Time' in df.columns:
                 time_col = 'start_Time'
            elif 'k' in df.columns: # Sometimes keys are short
                 time_col = 'k'
                 
            if time_col:
                 try:
                     # Dhan uses a custom integer format sometimes requiring conversion
                     # But convert_to_date_time helper is reliable if self.dhan is active
                     times = self.dhan.convert_to_date_time(df[time_col].tolist())
                     df['datetime'] = times
                 except Exception as e:
                     self.logger.warning(f"Time conversion failed: {e}")
                     # Fallback: if it's already epoch?
                     df['datetime'] = df[time_col]

                 df = df.set_index('datetime')
                 df.index = pd.to_datetime(df.index)
            else:
                 self.logger.warning("No time column found in Dhan response. Falling back to YFinance.")
                 return self.fetch_yfinance_data(symbol, timeframe, days, start_date, end_date)
                 
            # Rename Columns
            df = df.rename(columns={
                'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume' # Some APIs use short names
            })
            # Ensure standard names if keys were full names
            df = df.rename(columns={
                'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'
            })
            
            # Select required columns
            req_cols = ['open', 'high', 'low', 'close', 'volume']
            existing_cols = [c for c in req_cols if c in df.columns]
            df = df[existing_cols]
            
            # Ensure float
            df = df.astype(float)
            
            return df

        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {e}")
            return self.fetch_yfinance_data(symbol, timeframe, days, start_date, end_date)

    def fetch_yfinance_data(self, symbol, timeframe, days, start_date=None, end_date=None):
        """
        Fetches data from YFinance.
        """
        tf_map = {'1': '1m', '5': '5m', '15': '15m', '60': '1h'}
        interval = tf_map.get(timeframe, '1d')
        
        if symbol == "NIFTY":
            yf_symbol = "^NSEI"
        elif symbol == "BANKNIFTY":
            yf_symbol = "^NSEBANK"
        else:
            yf_symbol = f"{symbol}.NS"
            
        try:
            # Use start/end if provided
            if start_date and end_date:
                # yf.download expects YYYY-MM-DD strings usually
                df = yf.download(yf_symbol, start=start_date, end=end_date, interval=interval, progress=False)
            else:
                period = "1mo"
                if days <= 1: period = "1d"
                elif days <= 5: period = "5d"
                elif days <= 30: period = "1mo"
                elif days <= 90: period = "3mo"
                df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
            
            if df.empty:
                return None
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low", 
                "Close": "close", "Volume": "volume"
            })
            
            req = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in req):
                return None
                
            return df[req]

        except Exception as e:
            self.logger.error(f"YFinance Error: {e}")
            return None

    def get_market_status(self):
        return True
