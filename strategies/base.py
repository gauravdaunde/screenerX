from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    @abstractmethod
    def name(self):
        """Return strategy name"""
        pass

    @abstractmethod
    def description(self):
        """Return strategy description"""
        pass

    def check_signals(self, df):
        """
        Primary method for checking signals on a DataFrame.
        Used for Vectorized or Indicator-based strategies (VCP, MeanReversion).
        
        Args:
            df (pd.DataFrame): OHLCV Data
            
        Returns:
            list of dict: List of signals [{'time': ..., 'action': 'BUY', 'reason': ...}]
        """
        return []

    # --- Methods for Stateful / Multi-Timeframe Strategies (SMC) ---

    def analyze_htf(self, df_htf):
        """Analyze Higher Timeframe data (Optional)"""
        return None

    def on_ltf_candle(self, df_ltf, current_candle_index, htf_context, current_state, state_data):
        """
        Process a new LTF candle (Optional state machine logic).
        Returns: (next_state, signal, updated_state_data)
        """
        return current_state, None, state_data
