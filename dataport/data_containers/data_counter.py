"""
Counter Module

Provides a key-based counter data structure for accumulating values.
"""

from typing import Any, Callable, Dict, List, Literal, Optional, Union


class KeyCounter:
    """
    A key-based counter that accumulates numeric values for each unique key.
    
    This class provides an efficient way to track and accumulate counts or numeric
    values associated with different keys. When a key is added, if it doesn't exist
    it's created with the specified value; if it already exists, the counter is
    automatically incremented.
    
    The class supports configurable comparison operators for key matching:
    - 'equal': Exact match (default)
    - 'like': Key contains the search term (case-insensitive)
    - 'contains': Search term contains the key (case-insensitive)
    
    The main methods are:
    - add(key): Increments the key by 1 (simple counter)
    - increment(key, amount): Increments the key by a custom amount
    
    This makes it perfect for counting occurrences, tracking frequencies, or 
    accumulating values based on keys.
    
    Computational cost: $O(1)$ for add, increment, get, and bracket operations with 'equal'.
    $O(n)$ for 'like' and 'contains' operators where n is the number of unique keys.
    $O(n)$ for iteration operations where n is the number of unique keys.
    
    Example:
        >>> counter = KeyCounter()
        >>> counter.add("apple")  # First occurrence: creates with value 1
        1
        >>> counter.add("apple")  # Second occurrence: auto-increments to 2
        2
        >>> counter.increment("apple", 5)  # Third occurrence: auto-increments by 5
        7
        >>> counter.increment("banana", 3)  # New key: creates with value 3
        3
        >>> print(counter.total())
        10
        
        >>> # Using 'like' operator
        >>> counter = KeyCounter(match_operator='like')
        >>> counter.add("apple_red")
        >>> counter.add("apple_green")  # Matches 'apple' pattern
        >>> counter.get("apple")  # Returns first matching key's value
    """
    
    def __init__(
        self, 
        initial_data: Optional[Dict[Any, Union[int, float]]] = None,
        match_operator: Literal['equal', 'like', 'contains'] = 'equal'
    ) -> None:
        """
        Initialize the KeyCounter.
        
        Args:
            initial_data: Optional dictionary with initial key-value pairs.
                         Keys can be any hashable type, values must be numeric.
            match_operator: Comparison operator for key matching:
                          - 'equal': Exact match (default, $O(1)$)
                          - 'like': Key contains the search term, case-insensitive ($O(n)$)
                          - 'contains': Search term contains the key, case-insensitive ($O(n)$)
        
        Raises:
            TypeError: If initial_data values are not numeric.
            ValueError: If match_operator is not valid.
        
        Example:
            >>> counter = KeyCounter(match_operator='like')
            >>> counter.add("user_john_doe")
            >>> counter.get("john")  # Finds key containing 'john'
        """
        valid_operators = {'equal', 'like', 'contains'}
        if match_operator not in valid_operators:
            raise ValueError(
                f"Invalid match_operator: '{match_operator}'. "
                f"Must be one of {valid_operators}"
            )
        
        self._counters: Dict[Any, Union[int, float]] = {}
        self._match_operator: str = match_operator
        
        if initial_data:
            for key, value in initial_data.items():
                if not isinstance(value, (int, float)):
                    raise TypeError(f"Value for key '{key}' must be numeric, got {type(value)}")
                self._counters[key] = value
    
    def set_match_operator(self, operator: Literal['equal', 'like', 'contains']) -> None:
        """
        Change the match operator after initialization.
        
        This method allows you to switch between different comparison strategies
        without creating a new KeyCounter instance. Useful when you need to
        perform different types of lookups on the same data set.
        
        Args:
            operator: New comparison operator for key matching:
                     - 'equal': Exact match ($O(1)$)
                     - 'like': Key contains the search term, case-insensitive ($O(n)$)
                     - 'contains': Search term contains the key, case-insensitive ($O(n)$)
        
        Raises:
            ValueError: If operator is not valid.
        
        Example:
            >>> counter = KeyCounter(match_operator='equal')
            >>> counter.add("user_john_doe")
            >>> counter.get("john")  # Returns 0 (no exact match)
            0
            >>> counter.set_match_operator('like')
            >>> counter.get("john")  # Now finds "user_john_doe"
            1
            >>> counter.set_match_operator('contains')
            >>> counter.get("user_john_doe_admin")  # Finds "user_john_doe"
            1
        """
        valid_operators = {'equal', 'like', 'contains'}
        if operator not in valid_operators:
            raise ValueError(
                f"Invalid operator: '{operator}'. "
                f"Must be one of {valid_operators}"
            )
        self._match_operator = operator
    
    def get_match_operator(self) -> str:
        """
        Get the current match operator being used.
        
        Returns:
            The current match operator ('equal', 'like', or 'contains').
        
        Example:
            >>> counter = KeyCounter(match_operator='like')
            >>> counter.get_match_operator()
            'like'
        """
        return self._match_operator
    
    def _find_matching_key(self, search_key: Any) -> Optional[Any]:
        """
        Find a matching key based on the configured match operator.
        
        This internal method implements the three comparison strategies:
        - 'equal': Direct key lookup (hash-based, $O(1)$)
        - 'like': Key contains the search term (linear search, $O(n)$)
        - 'contains': Search term contains the key ($O(n)$)
        
        Args:
            search_key: The key or pattern to search for.
        
        Returns:
            The first matching key found, or None if no match exists.
        
        Cost: $O(1)$ for 'equal', $O(n)$ for 'like' and 'contains'.
        """
        if self._match_operator == 'equal':
            return search_key if search_key in self._counters else None
        
        search_str = str(search_key).lower()
        
        if self._match_operator == 'like':
            # Key contains the search term (substring match)
            for key in self._counters:
                if search_str in str(key).lower():
                    return key
        
        elif self._match_operator == 'contains':
            # Search term contains the key
            for key in self._counters:
                if str(key).lower() in search_str:
                    return key
        
        return None
    
    def _find_all_matching_keys(self, search_key: Any) -> List[Any]:
        """
        Find all matching keys based on the configured match operator.
        
        Args:
            search_key: The key or pattern to search for.
        
        Returns:
            List of all matching keys (empty list if no matches).
        
        Cost: $O(1)$ for 'equal', $O(n)$ for 'like' and 'contains'.
        """
        if self._match_operator == 'equal':
            return [search_key] if search_key in self._counters else []
        
        search_str = str(search_key).lower()
        matches = []
        
        if self._match_operator == 'like':
            # Key contains the search term
            for key in self._counters:
                if search_str in str(key).lower():
                    matches.append(key)
        
        elif self._match_operator == 'contains':
            # Search term contains the key
            for key in self._counters:
                if str(key).lower() in search_str:
                    matches.append(key)
        
        return matches
    
    def increment(self, key: Any, amount: Union[int, float] = 1) -> Union[int, float]:
        """
        Increment the counter for a given key by a specified amount.
        
        If the key doesn't exist, it's created with the specified amount.
        If the key already exists (based on match_operator), the amount is added.
        
        With 'like' or 'contains' operators, increments the first matching key.
        With 'equal' operator, performs exact key match.
        
        Args:
            key: The key to add/increment. Can be any hashable type.
            amount: The amount to set (if new) or add (if exists) (default: 1).
        
        Returns:
            The new value of the counter for this key.
        
        Raises:
            TypeError: If amount is not numeric.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("clicks")
            1
            >>> counter.increment("clicks")
            2
            >>> counter.increment("views", 10)
            10
            >>> counter.increment("views", 5)
            15
            
            >>> # With 'like' operator
            >>> counter = KeyCounter(match_operator='like')
            >>> counter.increment("user_john_doe", 1)
            >>> counter.increment("john", 1)  # Increments existing 'user_john_doe'
        """
        if not isinstance(amount, (int, float)):
            raise TypeError(f"Amount must be numeric, got {type(amount)}")
        
        matching_key = self._find_matching_key(key)
        
        if matching_key is None:
            self._counters[key] = amount
            return amount
        else:
            self._counters[matching_key] += amount
            return self._counters[matching_key]
        
        return self._counters[key]
    
    def add(self, key: Any) -> Union[int, float]:
        """
        Add a key to the counter, incrementing by 1.
        
        If the key doesn't exist, it's created with value 1.
        If the key already exists, it's incremented by 1.
        
        This is a convenience method equivalent to increment(key, 1).
        
        Args:
            key: The key to add/increment. Can be any hashable type.
        
        Returns:
            The new value of the counter for this key.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("clicks")
            1
            >>> counter.add("clicks")
            2
            >>> counter.add("clicks")
            3
        """
        return self.increment(key, 1)
    
    def decrement(self, key: Any, amount: Union[int, float] = 1) -> Union[int, float]:
        """
        Decrement the counter for a given key.
        
        If the key doesn't exist, it's created with the negative of the amount.
        If the key already exists, the amount is subtracted from the current value.
        
        Args:
            key: The key to decrement.
            amount: The amount to subtract from the counter (default: 1).
        
        Returns:
            The new value of the counter for this key.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("stock", 10)
            10
            >>> counter.decrement("stock", 3)
            7
            >>> counter.decrement("returns")  # New key with -1
            -1
        """
        return self.increment(key, -amount)
    
    def get(self, key: Any) -> Optional[Union[int, float]]:
        """
        Get the current value for a key using the configured match operator.
        
        With 'like' or 'contains' operators, returns the first matching key's value.
        With 'equal' operator, performs exact key match.
        
        Args:
            key: The key to retrieve.
        
        Returns:
            The current counter value for the key, or None if not found.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.get("missing")
            None
            >>> counter.get("apple")
            1
            
            >>> # With 'like' operator
            >>> counter = KeyCounter(match_operator='like')
            >>> counter.add("user_john_doe")
            >>> counter.get("john")  # Finds key containing 'john'
            1
        """
        matching_key = self._find_matching_key(key)
        
        if matching_key is None:
            return None
        
        return self._counters[matching_key]
    
    def get_all_matching(self, key: Any) -> Dict[Any, Union[int, float]]:
        """
        Get all keys and values that match the search pattern.
        
        Useful with 'like' or 'contains' operators when multiple keys may match.
        
        Args:
            key: The key or pattern to search for.
        
        Returns:
            Dictionary of all matching keys and their values.
        
        Example:
            >>> counter = KeyCounter(match_operator='like')
            >>> counter.add("user_john_doe")
            >>> counter.add("user_john_smith")
            >>> counter.add("admin_jane")
            >>> counter.get_all_matching("john")
            {'user_john_doe': 1, 'user_john_smith': 1}
        """
        matching_keys = self._find_all_matching_keys(key)
        return {k: self._counters[k] for k in matching_keys}
    
    def remove(self, key: Any) -> bool:
        """
        Remove a key from the counter.
        
        Args:
            key: The key to remove.
        
        Returns:
            True if the key was removed, False if it didn't exist.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("temp")
            >>> counter.remove("temp")
            True
            >>> counter.remove("nonexistent")
            False
        """
        if key in self._counters:
            del self._counters[key]
            return True
        return False
    
    def clear(self) -> None:
        """
        Remove all keys and reset all counters.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("a")
            >>> counter.add("b")
            >>> counter.clear()
            >>> counter.total()
            0
        """
        self._counters.clear()
    
    def total(self) -> Union[int, float]:
        """
        Calculate the sum of all counter values.
        
        Returns:
            The sum of all counter values.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 5)
            >>> counter.increment("b", 3)
            >>> counter.total()
            8
        """
        return sum(self._counters.values())
    
    def keys(self) -> List[Any]:
        """
        Get all keys in the counter.
        
        Returns:
            A list of all keys.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("x")
            >>> counter.add("y")
            >>> sorted(counter.keys())
            ['x', 'y']
        """
        return list(self._counters.keys())
    
    def values(self) -> List[Union[int, float]]:
        """
        Get all counter values.
        
        Returns:
            A list of all counter values.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter["a"] = 10
            >>> counter["b"] = 20
            >>> sorted(counter.values())
            [10, 20]
        """
        return list(self._counters.values())
    
    def items(self) -> List[tuple]:
        """
        Get all key-value pairs.
        
        Returns:
            A list of (key, value) tuples.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 5)
            >>> counter.items()
            [('a', 5)]
        """
        return list(self._counters.items())
    
    def most_common(self, n: Optional[int] = None) -> List[tuple]:
        """
        Get the n most common keys sorted by their counts.
        
        Args:
            n: Number of top items to return. If None, return all items.
        
        Returns:
            List of (key, count) tuples sorted by count in descending order.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 10)
            >>> counter.increment("b", 5)
            >>> counter.increment("c", 8)
            >>> counter.most_common(2)
            [('a', 10), ('c', 8)]
        """
        sorted_items = sorted(self._counters.items(), key=lambda x: x[1], reverse=True)
        
        if n is not None:
            return sorted_items[:n]
        return sorted_items
    
    def least_common(self, n: Optional[int] = None) -> List[tuple]:
        """
        Get the n least common keys sorted by their counts.
        
        Args:
            n: Number of bottom items to return. If None, return all items.
        
        Returns:
            List of (key, count) tuples sorted by count in ascending order.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 10)
            >>> counter.increment("b", 5)
            >>> counter.least_common(1)
            [('b', 5)]
        """
        sorted_items = sorted(self._counters.items(), key=lambda x: x[1])
        
        if n is not None:
            return sorted_items[:n]
        return sorted_items
    
    def sort(self, by: str = "count", order: str = "desc") -> List[tuple]:
        """
        Sort all items by the specified criterion and order.
        
        Args:
            by: Sorting criterion. Options:
                - "count" (default): Sort by counter value
                - "key": Sort by key
            order: Sorting order. Options:
                - "desc" (default): Descending order (high to low, Z to A)
                - "asc": Ascending order (low to high, A to Z)
        
        Returns:
            List of (key, count) tuples sorted according to parameters.
        
        Raises:
            ValueError: If 'by' or 'order' parameters are invalid.
        
        Cost: $O(n \log n)$ where n is the number of unique keys.
        
        Examples:
            >>> counter = KeyCounter()
            >>> counter.increment("c", 15)
            >>> counter.increment("a", 5)
            >>> counter.increment("b", 10)
            
            >>> # Sort by count (descending) - default
            >>> counter.sort()
            [('c', 15), ('b', 10), ('a', 5)]
            
            >>> # Sort by count (ascending)
            >>> counter.sort(by="count", order="asc")
            [('a', 5), ('b', 10), ('c', 15)]
            
            >>> # Sort by key (ascending)
            >>> counter.sort(by="key", order="asc")
            [('a', 5), ('b', 10), ('c', 15)]
            
            >>> # Sort by key (descending)
            >>> counter.sort(by="key", order="desc")
            [('c', 15), ('b', 10), ('a', 5)]
        """
        # Validate parameters
        valid_by = {"count", "key"}
        valid_order = {"asc", "desc"}
        
        if by not in valid_by:
            raise ValueError(f"Invalid 'by' parameter: '{by}'. Must be one of {valid_by}")
        
        if order not in valid_order:
            raise ValueError(f"Invalid 'order' parameter: '{order}'. Must be one of {valid_order}")
        
        # Determine sort key (0 for key, 1 for count)
        sort_index = 0 if by == "key" else 1
        
        # Determine reverse flag
        reverse = (order == "desc")
        
        # Perform sort
        return sorted(self._counters.items(), key=lambda x: x[sort_index], reverse=reverse)
    
    def __len__(self) -> int:
        """
        Get the number of unique keys using len() function.
        
        Returns:
            Number of unique keys in the counter.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.add("banana")
            >>> len(counter)
            2
        """
        return len(self._counters)
    
    def __contains__(self, key: Any) -> bool:
        """
        Check if a key exists in the counter using 'in' operator.
        
        Args:
            key: The key to check.
        
        Returns:
            True if the key exists, False otherwise.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> "apple" in counter
            True
            >>> "banana" in counter
            False
        """
        return key in self._counters
    
    def __getitem__(self, key: Any) -> Optional[Union[int, float]]:
        """
        Get counter value using bracket notation (counter[key]).
        
        Args:
            key: The key to retrieve.
        
        Returns:
            The counter value for the key, or None if not found.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter["apple"]
            1
            >>> counter["missing"]
            None
        """
        return self.get(key)
    
    def __setitem__(self, key: Any, value: Union[int, float]) -> None:
        """
        Set counter value using bracket notation (counter[key] = value).
        
        This directly assigns a value without auto-increment behavior.
        
        Args:
            key: The key to set.
            value: The numeric value to assign.
        
        Raises:
            TypeError: If value is not numeric.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter["apple"] = 10
            >>> counter["apple"]
            10
        """
        if not isinstance(value, (int, float)):
            raise TypeError(f"Value must be numeric, got {type(value)}")
        
        self._counters[key] = value
    
    def __iter__(self):
        """
        Iterate over keys in the counter using for loop.
        
        Returns:
            Iterator over keys.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.add("banana")
            >>> for key in counter:
            ...     print(key)
            apple
            banana
        """
        return iter(self._counters)
    
    def __repr__(self) -> str:
        """
        Get string representation of the counter.
        
        Returns:
            String representation showing the class name and current state.
        """
        return f"KeyCounter({dict(self._counters)})"
    
    def __str__(self) -> str:
        """
        Get human-readable string representation.
        
        Returns:
            Formatted string showing all key-value pairs.
        """
        if not self._counters:
            return "KeyCounter(empty)"
        
        items_str = ", ".join(f"'{k}': {v}" for k, v in self._counters.items())
        return f"KeyCounter({{{items_str}}})"
