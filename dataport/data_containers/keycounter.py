"""
Counter Module

Provides a key-based counter data structure for accumulating values with flexible matching strategies.
Uses SQLite in-memory database as internal storage for efficient data manipulation.
Leverages SQL native syntax for flexible key matching.
"""

from typing import Any, Callable, Dict, List, Optional, Union, Tuple
from .sqlite_mem import InMemorySQLite


class KeyCounter:
    """
    A key-based counter that accumulates numeric values for each unique key.
    
    This class provides an efficient way to track and accumulate counts or numeric
    values associated with different keys. When a key is added, if it doesn't exist
    it's created with the specified value; if it already exists, the counter is
    automatically incremented.
    
    Uses SQLite in-memory database for efficient data storage and manipulation.
    All key matching is done using exact match with SQL WHERE clauses.
    For flexible filtering, use the filter() method with custom SQL WHERE clauses.
    
    The main methods are:
    - add(key): Increments the key by 1 (simple counter)
    - increment(key, amount): Increments the key by a custom amount
    - get(key): Retrieves the counter value for a key (exact match)
    - filter(...): Filter counters using SQL WHERE clauses
    
    This makes it perfect for counting occurrences, tracking frequencies, or 
    accumulating values based on keys.
    
    Example:
        >>> # Exact match (only supported match type)
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
        
        >>> # Flexible filtering with SQL WHERE clauses
        >>> counter = KeyCounter()
        >>> counter["apple_red"] = 10
        >>> counter["apple_green"] = 5
        >>> counter["banana"] = 8
        >>> 
        >>> # Using WHERE with LIKE for pattern matching
        >>> filtered = counter.filter(where="key LIKE 'apple%'")
        >>> filtered.items()
        [('apple_red', 10), ('apple_green', 5)]
        >>> 
        >>> # Using WHERE with multiple conditions
        >>> filtered = counter.filter(where="key LIKE 'apple%' AND count >= 10")
        >>> filtered.items()
        [('apple_red', 10)]
    """
    
    def __init__(
        self, 
        initial_data: Optional[Dict[Any, Union[int, float]]] = None
    ) -> None:
        """
        Initialize the KeyCounter.
        
        Cost: $O(n)$ where n is the number of initial keys.
        
        Args:
            initial_data: Optional dictionary with initial key-value pairs.
                         Keys can be any hashable type, values must be numeric.
        
        Returns:
            None
        
        Raises:
            TypeError: If initial_data values are not numeric.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.get("apple")
            1
            
            >>> # With initial data
            >>> counter = KeyCounter(initial_data={"a": 5, "b": 10})
            >>> counter.get("a")
            5
        """
        # Initialize SQLite in-memory database
        self._db: InMemorySQLite = InMemorySQLite()
        self._table_name: str = "counters"
        
        # Create table: key (TEXT PRIMARY KEY), count (REAL)
        self._db.create_table(
            self._table_name,
            "key TEXT PRIMARY KEY, count REAL NOT NULL DEFAULT 0"
        )
        
        # Insert initial data if provided
        if initial_data:
            for key, value in initial_data.items():
                if not isinstance(value, (int, float)):
                    raise TypeError(
                        f"All values must be numeric. Key '{key}' has value of type {type(value).__name__}"
                    )
                self._db.insert_data(
                    self._table_name,
                    "key, count",
                    (str(key), float(value))
                )
    
    def _fetch(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """
        Execute a query and return results as a list of tuples.
        
        This is a helper method to wrap execute_query and fetchall().
        
        Args:
            query: SQL query string
            params: Optional tuple of parameters
        
        Returns:
            List[tuple]: Query results as list of tuples, empty list if no results
        """
        try:
            cursor = self._db.execute_query(query, params if params else ())
            return cursor.fetchall() if cursor else []
        except Exception:
            return []
    
    def _key_exists(self, key: Any, condition: Optional[str] = None) -> bool:
        """
        Check if a key exists in the counter using exact match.
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to search for.
            condition: Optional SQL WHERE condition to apply in addition to key match.
                      Example: "count > 5"
        
        Returns:
            bool: True if the key exists and meets the condition, False otherwise.
        
        Raises:
            None
        """
        try:
            search_str = str(key)
        except (TypeError, AttributeError):
            return False
        
        if condition:
            query = f"SELECT 1 FROM {self._table_name} WHERE key = ? AND ({condition}) LIMIT 1"
        else:
            query = f"SELECT 1 FROM {self._table_name} WHERE key = ? LIMIT 1"
        result = self._fetch(query, (search_str,))
        return len(result) > 0
    
    def increment(self, key: Any, amount: Union[int, float] = 1, condition: Optional[str] = None) -> Union[int, float]:
        """
        Increment the counter for a given key by a specified amount.
        
        If the key doesn't exist, it's created with the specified amount.
        If the key already exists and meets the condition, the amount is added.
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to add/increment. Can be any hashable type.
            amount: The amount to set (if new) or add (if exists) (default: 1).
            condition: Optional SQL WHERE condition that must be met to increment.
                      Example: "count < 100" (only increment if current count < 100)
        
        Returns:
            Union[int, float]: The new value of the counter for this key.
        
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
            >>> counter.increment("limited", 1, condition="count < 5")
            1
        """
        if not isinstance(amount, (int, float)):
            raise TypeError(f"amount must be numeric, got {type(amount).__name__}")
        
        try:
            key_str = str(key)
        except (TypeError, AttributeError):
            raise ValueError(f"Key must be convertible to string, got {type(key).__name__}")
        
        # Check if key exists (and meets condition if provided)
        if condition:
            check_query = f"SELECT key,count FROM {self._table_name} WHERE {condition}"
            current = self._fetch(check_query, ())
        else:
            check_query = f"SELECT key,count FROM {self._table_name} WHERE key = ?"
            current = self._fetch(check_query, (key_str,))
        
        if current and len(current) > 0:
            # Keys exist and meet condition, update them
            for row in current:
                new_value = row[1] + amount
                self._db.update_data(self._table_name, "count = ?", "key = ?", (new_value, row[0]))
            return new_value
        else:
            # Key doesn't exist, insert it
            self._db.insert_data(self._table_name, "key, count", (key_str, float(amount)))
            return amount
    
    def add(self, key: Any, condition: Optional[str] = None) -> Union[int, float]:
        """
        Add a key to the counter, incrementing by 1.
        
        If the key doesn't exist, it's created with value 1.
        If the key already exists and meets the condition, it's incremented by 1.
        
        This is a convenience method equivalent to increment(key, 1, condition).
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to add/increment. Can be any hashable type.
            condition: Optional SQL WHERE condition that must be met to increment.
                      Example: "count < 100"
        
        Returns:
            Union[int, float]: The new value of the counter for this key.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("clicks")
            1
            >>> counter.add("clicks")
            2
            >>> counter.add("clicks")
            3
            >>> counter.add("limited", condition="count < 5")
            1
        """
        return self.increment(key, 1, condition)
    
    def decrement(self, key: Any, amount: Union[int, float] = 1, condition: Optional[str] = None) -> Union[int, float]:
        """
        Decrement the counter for a given key.
        
        If the key doesn't exist, it's created with the negative of the amount.
        If the key already exists and meets the condition, the amount is subtracted from the current value.
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to decrement.
            amount: The amount to subtract from the counter (default: 1).
            condition: Optional SQL WHERE condition that must be met to decrement.
                      Example: "count > 0" (only decrement if positive)
        
        Returns:
            Union[int, float]: The new value of the counter for this key.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("stock", 10)
            10
            >>> counter.decrement("stock", 3)
            7
            >>> counter.decrement("returns")  # New key with -1
            -1
            >>> counter.decrement("stock", 1, condition="count > 5")
            6
        """
        return self.increment(key, -amount, condition)
    
    def get(self, key: Any, condition: Optional[str] = None) -> Optional[Union[int, float]]:
        """
        Get the current value for a key (exact match).
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to retrieve.
            condition: Optional SQL WHERE condition that must be met.
                      Example: "count > 5"
        
        Returns:
            Optional[Union[int, float]]: The current counter value for the key, or None if not found or doesn't meet condition.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.get("apple")
            1
            
            >>> counter.get("banana")
            None
            
            >>> counter["test"] = 10
            >>> counter.get("test", condition="count > 5")
            10
            >>> counter.get("test", condition="count > 15")
            None
        """
        if condition:
            query = f"SELECT key,count FROM {self._table_name} WHERE {condition}"
            result = self._fetch(query, ())
        else:
            query = f"SELECT key,count FROM {self._table_name} WHERE key = ?"
            result = self._fetch(query, (str(key),))
        
        return result if result and len(result) > 0 else None
    
    def remove(self, key: Any, condition: Optional[str] = None) -> bool:
        """
        Remove a key from the counter.
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to remove.
            condition: Optional SQL WHERE condition that must be met to remove.
                      Example: "count < 5" (only remove if count is less than 5)
        
        Returns:
            bool: True if the key was removed, False if it didn't exist or didn't meet condition.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("temp")
            >>> counter.remove("temp")
            True
            >>> counter.remove("nonexistent")
            False
            >>> counter["test"] = 10
            >>> counter.remove("test", condition="count < 5")
            False
            >>> counter.remove("test", condition="count > 5")
            True
        """
        try:
            if condition:
                where_clause = f"{condition}"
            else:
                where_clause = "key = ?"
            rows_deleted = self._db.delete_data(self._table_name, where_clause, (str(key),))
            return rows_deleted > 0
        except Exception:
            return False
    
    def clear(self) -> None:
        """
        Remove all keys and reset all counters.
        
        Cost: $O(n)$ where n is the number of keys.
        
        Args:
            None
        
        Returns:
            None
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("a")
            >>> counter.add("b")
            >>> counter.clear()
            >>> counter.total()
            0
        """
        # Delete all rows from table
        self._db.delete_data(self._table_name, "1=1", ())
    
    def total(self, condition: Optional[str] = None) -> Union[int, float]:
        """
        Calculate the sum of all counter values.
        
        Cost: $O(n)$ where n is the number of unique keys.
        
        Args:
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            Union[int, float]: The sum of all counter values.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 5)
            >>> counter.increment("b", 3)
            >>> counter.total()
            8
            >>> counter.total(condition="count > 3")
            5
        """
        if condition:
            query = f"SELECT SUM(count) FROM {self._table_name} WHERE {condition}"
        else:
            query = f"SELECT SUM(count) FROM {self._table_name}"
        result = self._fetch(query)
        return result[0][0] if result and result[0][0] is not None else 0
    
    def keys(self, condition: Optional[str] = None) -> List[Any]:
        """
        Get all keys in the counter.
        
        Cost: $O(n)$ where n is the number of unique keys.
        
        Args:
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            List[Any]: A list of all keys.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("x")
            >>> counter.add("y")
            >>> sorted(counter.keys())
            ['x', 'y']
            >>> counter.keys(condition="key LIKE 'x%'")
            ['x']
        """
        if condition:
            query = f"SELECT key FROM {self._table_name} WHERE {condition}"
        else:
            query = f"SELECT key FROM {self._table_name}"
        result = self._fetch(query)
        return [row[0] for row in result]
    
    def values(self, condition: Optional[str] = None) -> List[Union[int, float]]:
        """
        Get all counter values.
        
        Cost: $O(n)$ where n is the number of unique keys.
        
        Args:
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            List[Union[int, float]]: A list of all counter values.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter["a"] = 10
            >>> counter["b"] = 20
            >>> sorted(counter.values())
            [10, 20]
            >>> counter.values(condition="count >= 20")
            [20]
        """
        if condition:
            query = f"SELECT count FROM {self._table_name} WHERE {condition}"
        else:
            query = f"SELECT count FROM {self._table_name}"
        result = self._fetch(query)
        return [row[0] for row in result]
    
    def items(self, condition: Optional[str] = None) -> List[tuple]:
        """
        Get all key-value pairs.
        
        Cost: $O(n)$ where n is the number of unique keys.
        
        Args:
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            List[tuple]: A list of (key, value) tuples.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 5)
            >>> counter.items()
            [('a', 5)]
            >>> counter.items(condition="count > 3")
            [('a', 5)]
        """
        if condition:
            query = f"SELECT key, count FROM {self._table_name} WHERE {condition}"
        else:
            query = f"SELECT key, count FROM {self._table_name}"
        result = self._fetch(query)
        return [(row[0], row[1]) for row in result]
    
    def most_common(self, n: Optional[int] = None, condition: Optional[str] = None) -> List[tuple]:
        """
        Get the n most common keys sorted by their counts.
        
        Cost: $O(n \\log n)$ where n is the number of unique keys.
        
        Args:
            n: Number of top items to return. If None, return all items.
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            List[tuple]: List of (key, count) tuples sorted by count in descending order.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 10)
            >>> counter.increment("b", 5)
            >>> counter.increment("c", 8)
            >>> counter.most_common(2)
            [('a', 10), ('c', 8)]
            >>> counter.most_common(condition="count > 6")
            [('a', 10), ('c', 8)]
        """
        if condition:
            query = f"SELECT key, count FROM {self._table_name} WHERE {condition} ORDER BY count DESC"
        else:
            query = f"SELECT key, count FROM {self._table_name} ORDER BY count DESC"
        
        if n is not None:
            query += f" LIMIT {int(n)}"
        
        result = self._fetch(query)
        return [(row[0], row[1]) for row in result]
    
    def least_common(self, n: Optional[int] = None, condition: Optional[str] = None) -> List[tuple]:
        """
        Get the n least common keys sorted by their counts.
        
        Cost: $O(n \\log n)$ where n is the number of unique keys.
        
        Args:
            n: Number of bottom items to return. If None, return all items.
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            List[tuple]: List of (key, count) tuples sorted by count in ascending order.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.increment("a", 10)
            >>> counter.increment("b", 5)
            >>> counter.least_common(1)
            [('b', 5)]
            >>> counter.least_common(condition="count < 10")
            [('b', 5)]
        """
        if condition:
            query = f"SELECT key, count FROM {self._table_name} WHERE {condition} ORDER BY count ASC"
        else:
            query = f"SELECT key, count FROM {self._table_name} ORDER BY count ASC"
        
        if n is not None:
            query += f" LIMIT {int(n)}"
        
        result = self._fetch(query)
        return [(row[0], row[1]) for row in result]
    
    def sort(self, by: str = "count", order: str = "desc", condition: Optional[str] = None) -> List[tuple]:
        """
        Sort all items by the specified criterion and order.
        
        Cost: $O(n \\log n)$ where n is the number of unique keys.
        
        Args:
            by: Sorting criterion. Options:
                - "count" (default): Sort by counter value
                - "key": Sort by key
            order: Sorting order. Options:
                - "desc" (default): Descending order (high to low, Z to A)
                - "asc": Ascending order (low to high, A to Z)
            condition: Optional SQL WHERE condition to filter keys.
                      Example: "key LIKE 'apple%'" or "count > 5"
        
        Returns:
            List[tuple]: List of (key, count) tuples sorted according to parameters.
        
        Raises:
            ValueError: If 'by' or 'order' parameters are invalid.
        
        Example:
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
            
            >>> # Sort with condition
            >>> counter.sort(by="count", order="desc", condition="count > 7")
            [('c', 15), ('b', 10)]
        """
        # Validate parameters
        valid_by = {"count", "key"}
        valid_order = {"asc", "desc"}
        
        if by not in valid_by:
            raise ValueError(f"Invalid 'by' parameter: {by}. Valid values: {valid_by}")
        
        if order not in valid_order:
            raise ValueError(f"Invalid 'order' parameter: {order}. Valid values: {valid_order}")
        
        # Build SQL query with ORDER BY
        sql_order = "ASC" if order == "asc" else "DESC"
        
        if condition:
            query = f"SELECT key, count FROM {self._table_name} WHERE {condition} ORDER BY {by} {sql_order}"
        else:
            query = f"SELECT key, count FROM {self._table_name} ORDER BY {by} {sql_order}"
        
        result = self._fetch(query)
        return [(row[0], row[1]) for row in result]
    
    def is_loaded(self) -> bool:
        """
        Check if the counter has any data loaded.
        
        Cost: $O(1)$
        
        Args:
            None
        
        Returns:
            bool: True if the counter contains at least one key, False otherwise.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.is_loaded()
            False
            >>> counter.add("item")
            >>> counter.is_loaded()
            True
        """
        query = f"SELECT COUNT(*) FROM {self._table_name}"
        result = self._fetch(query)
        return result[0][0] > 0 if result else False
    
    def __len__(self) -> int:
        """
        Get the number of unique keys using len() function.
        
        Cost: $O(1)$
        
        Args:
            None
        
        Returns:
            int: Number of unique keys in the counter.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.add("banana")
            >>> len(counter)
            2
        """
        query = f"SELECT COUNT(*) FROM {self._table_name}"
        result = self._fetch(query)
        return result[0][0] if result else 0
    
    def __contains__(self, key: Any) -> bool:
        """
        Check if a key exists in the counter using 'in' operator.
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to check for existence.
        
        Returns:
            bool: True if the key exists, False otherwise.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> "apple" in counter
            True
            >>> "banana" in counter
            False
        """
        query = f"SELECT COUNT(*) FROM {self._table_name} WHERE key = ?"
        result = self._fetch(query, (str(key),))
        return result[0][0] > 0 if result else False
    
    def __getitem__(self, key: Any) -> Optional[Union[int, float]]:
        """
        Get counter value using bracket notation (counter[key]).
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to retrieve.
        
        Returns:
            Optional[Union[int, float]]: The counter value, or None if not found.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter["apple"]
            1
            >>> counter["banana"]  # Returns None
            None
        """
        return self.get(key)
    
    def __setitem__(self, key: Any, value: Union[int, float]) -> None:
        """
        Set counter value using bracket notation (counter[key] = value).
        
        Cost: $O(1)$ with PRIMARY KEY index.
        
        Args:
            key: The key to set.
            value: The numeric value to assign.
        
        Returns:
            None
        
        Raises:
            TypeError: If value is not numeric.
        
        Example:
            >>> counter = KeyCounter()
            >>> counter["apple"] = 10
            >>> counter["apple"]
            10
        """
        if not isinstance(value, (int, float)):
            raise TypeError(f"Value must be numeric, got {type(value).__name__}")
        
        # Use INSERT OR REPLACE (UPSERT) to set value
        try:
            # Check if key exists first
            query = f"SELECT COUNT(*) FROM {self._table_name} WHERE key = ?"
            result = self._fetch(query, (str(key),))
            exists = result[0][0] > 0 if result else False
            
            if exists:
                # Update existing key
                self._db.update_data(self._table_name, "count = ?", "key = ?", (float(value), str(key)))
            else:
                # Insert new key
                self._db.insert_data(self._table_name, "key, count", (str(key), float(value)))
        except Exception:
            # Fallback to insert if update fails
            try:
                self._db.insert_data(self._table_name, "key, count", (str(key), float(value)))
            except Exception:
                pass
    
    def __iter__(self):
        """
        Iterate over keys in the counter.
        
        Cost: $O(1)$ per iteration step, $O(n)$ total.
        
        Args:
            None
        
        Returns:
            Iterator over keys.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("a")
            >>> counter.add("b")
            >>> for key in counter:
            ...     print(key)
            a
            b
        """
        return iter(self.keys())
    
    def __repr__(self) -> str:
        """
        Return string representation of the counter.
        
        Cost: $O(n)$ where n is the number of keys.
        
        Args:
            None
        
        Returns:
            str: String representation showing internal state.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> repr(counter)
            "KeyCounter({'apple': 1})"
        """
        items_dict = dict(self.items())
        return f"KeyCounter({items_dict})"
    
    def __str__(self) -> str:
        """
        Return user-friendly string representation.
        
        Cost: $O(n)$ where n is the number of keys.
        
        Args:
            None
        
        Returns:
            str: Formatted string showing all key-value pairs.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter["a"] = 5
            >>> counter["b"] = 3
            >>> print(counter)
            KeyCounter: 2 keys, total=8
              a: 5
              b: 3
        """
        count = len(self)
        if count == 0:
            return "KeyCounter: empty"
        
        total = self.total()
        lines = [f"KeyCounter: {count} keys, total={total}"]
        for key, value in self.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)
       
    def filter(
        self, 
        min_count: Optional[Union[int, float]] = None, 
        max_count: Optional[Union[int, float]] = None,
        where: Optional[str] = None
    ) -> 'KeyCounter':
        """
        Filter counter by count range or custom SQL WHERE clause.
        
        Cost: $O(n)$ where n is the number of keys.
        
        Args:
            min_count: Minimum count threshold (inclusive). If None, no lower bound.
            max_count: Maximum count threshold (inclusive). If None, no upper bound.
            where: Optional SQL WHERE clause for custom filtering.
                   If provided, overrides min_count and max_count.
                   Examples:
                   - "key LIKE 'apple%'"
                   - "key LIKE 'apple%' AND count > 5"
                   - "count BETWEEN 10 AND 20"
                   - "key IN ('apple', 'banana')"
        
        Returns:
            KeyCounter: New KeyCounter with filtered data.
        
        Raises:
            None
        
        Example:
            >>> counter = KeyCounter()
            >>> counter["apple_red"] = 10
            >>> counter["apple_green"] = 5
            >>> counter["banana"] = 8
            
            >>> # Using min/max count
            >>> filtered = counter.filter(min_count=7)
            >>> filtered.items()
            [('apple_red', 10), ('banana', 8)]
            
            >>> # Using custom WHERE with LIKE
            >>> filtered = counter.filter(where="key LIKE 'apple%'")
            >>> filtered.items()
            [('apple_red', 10), ('apple_green', 5)]
            
            >>> # Using combined WHERE conditions
            >>> filtered = counter.filter(where="key LIKE 'apple%' AND count >= 10")
            >>> filtered.items()
            [('apple_red', 10)]
            
            >>> # Using BETWEEN
            >>> filtered = counter.filter(where="count BETWEEN 8 AND 12")
            >>> filtered.items()
            [('apple_red', 10), ('banana', 8)]
        """
        # Priority: where > min/max_count
        
        # Use custom WHERE clause if provided
        if where is not None:
            query = f"SELECT key, count FROM {self._table_name} WHERE {where}"
            result = self._fetch(query)
        
        # Build SQL WHERE clause from min/max count
        else:
            where_conditions = []
            params = []
            
            if min_count is not None:
                where_conditions.append("count >= ?")
                params.append(min_count)
            
            if max_count is not None:
                where_conditions.append("count <= ?")
                params.append(max_count)
            
            # Execute query to get filtered data
            where_sql = " AND ".join(where_conditions) if where_conditions else "1=1"
            query = f"SELECT key, count FROM {self._table_name} WHERE {where_sql}"
            result = self._fetch(query, tuple(params) if params else None)
        
        # Create new KeyCounter with filtered data
        new_counter = KeyCounter()
        
        # Insert filtered data into new counter
        if result:
            for row in result:
                new_counter._db.insert_data(
                    new_counter._table_name,
                    "key, count",
                    (row[0], row[1])
                )
        
        return new_counter
    
    def destroy(self) -> None:
        """
        Destroy the KeyCounter and release all memory used by the SQLite database.
        
        Description:
            Closes the SQLite in-memory database connection and releases all associated
            memory. After calling this method, the KeyCounter instance should not be used.
            This is useful for explicitly freeing memory when you're done with a counter,
            especially when dealing with large datasets.
            
            The method is idempotent - calling it multiple times is safe and has no effect
            after the first call.
        
        Cost: $O(1)$
        
        Args:
            None
        
        Returns:
            None
        
        Raises:
            None
        
        Example Usage:
            >>> counter = KeyCounter()
            >>> counter.add("apple")
            >>> counter.add("banana")
            >>> print(len(counter))
            2
            >>> 
            >>> # When done with the counter, destroy it to free memory
            >>> counter.destroy()
            >>> # counter should not be used after this point
        """
        if hasattr(self, '_db') and self._db is not None:
            self._db.close()
            self._db = None
    

