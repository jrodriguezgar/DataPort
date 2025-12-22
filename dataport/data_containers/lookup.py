"""
Lookup Module

Description:
    Provides bidirectional lookup structures with indexed access for O(1) operations.
    Manages code-description mappings with optional additional fields.

Classes:
    LookUp: Manages bidirectional lookup with code, description, and additional fields

Author:
    guardianZ Identity Management System

Date:
    2025-01-15
"""

from typing import List, Dict, Any, Union, Tuple, Optional, Callable


class LookUp:
    """
    Manages bidirectional lookup with indexed structure for O(1) lookups.
    
    Description:
        Encapsulates lookup table functionality with:
        - Three flexible input formats: dicts, lists with headers, lists without headers
        - Code to item mapping (primary lookup with configurable field name)
        - Dynamic index creation for any field
        - Configurable text formatting (upper, lower, capitalize)
        - Memory-efficient internal structure
    
    Input Formats:
        1. List of dictionaries (most Pythonic):
           [{'code': 'ES', 'name': 'Spain'}, ...]
           
        2. List of lists/tuples with headers:
           [('ES', 'Spain'), ...] + headers=['code', 'name']
           
        3. List of lists/tuples without headers (auto-generated):
           [('ES', 'Spain'), ...] → generates ['code', 'description', 'field_2', ...]
    
    Attributes:
        _cache (dict): Indexed structure with 'data', primary index, and custom indices
        _field_names (list): Ordered list of field names
        _loaded (bool): Indicates if data has been loaded
        _custom_indices (dict): Dictionary of custom index names and their format configurations
        _code_field_name (str): Name of the primary index field (configurable, set during load)
        _code_index (int): Position of code field (for list/tuple input)
        
    Cache Structure:
        {
            'data': [list of items as dicts],
            '<primary_field_name>': {formatted_code: item_dict},  # e.g., 'country_code', 'sku', etc.
            '<custom_field>': {formatted_value: formatted_code}   # Created dynamically on demand
        }
    
    Cost:
        - Lookup by code: O(1)
        - Lookup by custom indexed field: O(1)
        - Create new index: O(n) where n is number of items
        - Load data: O(n) where n is number of items
    
    Examples:
        >>> # Format 1: List of dictionaries
        >>> lookup = LookUp(code_format='upper')
        >>> data = [
        ...     {'country_code': 'es', 'name': 'Spain', 'currency': 'EUR'},
        ...     {'country_code': 'fr', 'name': 'France', 'currency': 'EUR'}
        ... ]
        >>> lookup.load(data, code_field='country_code')
        >>> lookup.get_item_by_code('es')
        {'country_code': 'ES', 'name': 'Spain', 'currency': 'EUR'}
        
        >>> # Format 2: List with headers
        >>> lookup = LookUp(code_format='upper')
        >>> lookup.load([('es', 'Spain', 'EUR'), ('fr', 'France', 'EUR')],
        ...             code_field=0,
        ...             headers=['country_code', 'name', 'currency'])
        >>> lookup.get_item_by_code('es')
        {'country_code': 'ES', 'name': 'Spain', 'currency': 'EUR'}
        
        >>> # Format 3: List without headers (auto-generated)
        >>> lookup = LookUp(code_format='upper')
        >>> lookup.load([('es', 'Spain', 'EUR'), ('fr', 'France', 'EUR')],
        ...             code_field=0)
        >>> lookup.get_item_by_code('es')
        {'code': 'ES', 'field_1': 'Spain', 'field_2': 'EUR'}
        
        >>> # Dynamic index creation
        >>> lookup.create_index('currency')
        >>> lookup.get_code_by_index('currency', 'EUR')
        'ES'  # or 'FR' (first match)
        
        >>> # Custom search with callable for specialized strategies
        >>> def custom_search(code, formatted_code):
        ...     cache = lookup._cache.get(lookup._code_field_name, {})
        ...     return cache.get(formatted_code)
        >>> lookup.get_item_by_code('es', search_fn=custom_search)
        {'country_code': 'ES', 'name': 'Spain', 'currency': 'EUR'}
    """

    # Valid formatting options
    _VALID_FORMATS = [None, 'upper', 'lower', 'capitalize']

    def __init__(self, code_format: Optional[str] = None):
        """
        Initialize the LookUp instance with optional formatting.
        
        Description:
            Creates an empty indexed lookup structure with configurable formatting
            for the primary code field. Any additional fields can be indexed
            dynamically using create_index() with their own formatting options.
        
        Args:
            code_format: Format for code values ('upper', 'lower', 'capitalize', or None)
        
        Raises:
            ValueError: If format parameter contains an invalid option
        
        Example:
            >>> lookup = LookUp(code_format='upper')
            >>> # For other fields, use: lookup.create_index('description', format_type='lower')
        
        Cost:
            O(1)
        """
        # Validate format option
        self._validate_format(code_format)

        # Store formatting option
        self._code_format = code_format

        # Initialize indexed cache structure
        self._cache: Dict[str, Any] = {
            'data': []
        }
        
        # Store field metadata
        self._field_names: List[str] = []
        self._code_index: Optional[int] = None
        self._code_field_name: Optional[str] = None  # Name of the primary index field
        self._custom_indices: Dict[str, Optional[str]] = {}  # {field_name: format_type}
        self._loaded = False

    def _validate_format(self, format_value: Optional[str]) -> None:
        """
        Validate format parameter value.
        
        Description:
            Ensures format value is one of the allowed options.
        
        Args:
            format_value: Format string to validate
        
        Raises:
            ValueError: If format_value is not in _VALID_FORMATS
        
        Cost:
            O(1)
        """
        if format_value not in self._VALID_FORMATS:
            raise ValueError(
                f"Invalid format: '{format_value}'. Must be one of {self._VALID_FORMATS}."
            )

    def _apply_format(self, value: Any, format_type: Optional[str]) -> Any:
        """
        Apply formatting to a value if applicable.
        
        Description:
            Applies the specified format transformation to string values.
            Non-string values are returned unchanged.
        
        Args:
            value: Value to format
            format_type: Format to apply ('upper', 'lower', 'capitalize', or None)
        
        Returns:
            Formatted value (or original if not a string or format is None)
        
        Cost:
            O(n) where n is the length of the string (for Python string operations)
        """
        if not isinstance(value, str) or format_type is None:
            return value
        
        if format_type == 'upper':
            return value.upper()
        elif format_type == 'lower':
            return value.lower()
        elif format_type == 'capitalize':
            return value.capitalize()
        
        return value

    def load(self,
             data: Union[List[Dict[str, Any]], List[List[Any]], List[Tuple[Any, ...]]],
             code_field: Union[str, int] = 0,
             headers: Optional[List[str]] = None) -> None:
        """
        Load data into the indexed cache.
        
        Description:
            Supports three data formats:
            1. List of dictionaries: Uses dict keys as field names
            2. List of lists/tuples with headers: Uses provided headers
            3. List of lists/tuples without headers: Auto-generates field names
            
            Creates primary index using the specified code field.
            For additional field indexing, use create_index() after loading.
        
        Args:
            data: Data to load in one of three formats:
                  - List[Dict]: [{'code': 'ES', 'name': 'Spain'}, ...]
                  - List[List/Tuple] with headers: [['ES', 'Spain'], ...]
                  - List[List/Tuple] without headers: Auto-generates names
            code_field: Primary index field (field name for dicts, index for lists/tuples)
            headers: Field names for list/tuple data. Ignored for dict data
        
        Raises:
            ValueError: If data structure is invalid or field references are incorrect
        
        Example:
            >>> # Format 1: List of dictionaries
            >>> lookup = LookUp(code_format='upper')
            >>> lookup.load([
            ...     {'country_code': 'es', 'name': 'Spain', 'currency': 'EUR'},
            ...     {'country_code': 'fr', 'name': 'France', 'currency': 'EUR'}
            ... ], code_field='country_code')
            >>> # Optionally create index for 'name' field
            >>> lookup.create_index('name', 'lower')
            
            >>> # Format 2: List of tuples with headers
            >>> lookup.load([('es', 'Spain', 'EUR'), ('fr', 'France', 'EUR')],
            ...             code_field=0,
            ...             headers=['country_code', 'name', 'currency'])
            
            >>> # Format 3: List of tuples without headers (auto-generated)
            >>> lookup.load([('ES', 'Spain'), ('FR', 'France')],
            ...             code_field=0)
            >>> # Creates fields: 'code', 'field_1'
        
        Cost:
            O(n) where n is the number of items in data
        """
        # Clear existing data
        self._cache = {'data': []}
        self._custom_indices = {}
        self._loaded = False
        
        if not data:
            return
        
        # Detect data format
        first_item = data[0]
        is_dict_format = isinstance(first_item, dict)
        
        if is_dict_format:
            # Format 1: List of dictionaries
            self._load_from_dicts(data, code_field)
        else:
            # Format 2 or 3: List of lists/tuples
            self._load_from_lists(data, code_field, headers)
        
        self._loaded = True

    def _load_from_dicts(self,
                         data: List[Dict[str, Any]],
                         code_field: str) -> None:
        """
        Load data from list of dictionaries.
        
        Args:
            data: List of dictionaries
            code_field: Name of the field to use as primary index
        """
        # Validate code_field exists
        if code_field not in data[0]:
            raise ValueError(f"Code field '{code_field}' not found in data")
        
        # Extract field names from first dict
        self._field_names = list(data[0].keys())
        self._code_field_name = code_field
        self._code_index = self._field_names.index(code_field)
        
        # Create primary index
        self._cache[self._code_field_name] = {}
        
        # Load each item
        for item_dict in data:
            # Apply formatting to code
            code_raw = item_dict[code_field]
            code_formatted = self._apply_format(code_raw, self._code_format)
            
            # Build formatted item dict
            formatted_item = {}
            for field_name, value in item_dict.items():
                if field_name == code_field:
                    formatted_item[field_name] = code_formatted
                else:
                    formatted_item[field_name] = value
            
            # Add to cache
            self._cache['data'].append(formatted_item)
            self._cache[self._code_field_name][code_formatted] = formatted_item

    def _load_from_lists(self,
                         data: Union[List[List[Any]], List[Tuple[Any, ...]]],
                         code_field: int,
                         headers: Optional[List[str]]) -> None:
        """
        Load data from list of lists/tuples.
        
        Args:
            data: List of lists or tuples
            code_field: Index of the code field
            headers: Optional field names
        """
        # Validate indices
        item_length = len(data[0])
        
        if code_field >= item_length:
            raise ValueError(f"Code index {code_field} out of bounds for item length {item_length}")
        
        self._code_index = code_field
        
        # Determine field names
        if headers:
            if len(headers) != item_length:
                raise ValueError(f"Headers length ({len(headers)}) must match item length ({item_length})")
            self._field_names = headers
        else:
            # Auto-generate field names
            self._field_names = []
            for idx in range(item_length):
                if idx == code_field:
                    self._field_names.append('code')
                else:
                    self._field_names.append(f'field_{idx}')
        
        # Set primary index field name
        self._code_field_name = self._field_names[code_field]
        self._cache[self._code_field_name] = {}
        
        # Load each item
        for item in data:
            self._add_list_item(item)

    def _add_list_item(self, item: Union[List[Any], Tuple[Any, ...]]) -> None:
        """
        Add a single list/tuple item to the cache.
        
        Args:
            item: List or tuple representing the item
        """
        # Extract and format code
        code_raw = item[self._code_index]
        code_formatted = self._apply_format(code_raw, self._code_format)
        
        # Build item dictionary
        item_dict = {}
        for idx, field_name in enumerate(self._field_names):
            if idx == self._code_index:
                item_dict[field_name] = code_formatted
            else:
                item_dict[field_name] = item[idx]
        
        # Add to cache
        self._cache['data'].append(item_dict)
        self._cache[self._code_field_name][code_formatted] = item_dict
        
        # Index custom indexed fields
        for field_name, format_type in self._custom_indices.items():
            if field_name in item_dict:
                field_value = item_dict[field_name]
                field_value_formatted = self._apply_format(field_value, format_type)
                
                if field_name not in self._cache:
                    self._cache[field_name] = {}
                
                self._cache[field_name][field_value_formatted] = code_formatted

    def add_item(
        self,
        item: Union[Dict[str, Any], List[Any], Tuple[Any, ...]],
        code_field: Union[str, int, None] = None,
        headers: Optional[List[str]] = None
    ) -> None:
        """
        Add a single item to the cache.
        
        Description:
            Accepts dictionaries or lists/tuples. Applies formatting to designated fields
            and adds to primary and custom indices. If the lookup is uninitialized,
            the code_field parameter is required to set up the structure.
        
        Args:
            item: Item to add (dict, list, or tuple)
            code_field: Primary index field (required if lookup is uninitialized).
                       For dicts: field name (str). For lists/tuples: index (int)
            headers: Field names for list/tuple data (optional, only used if uninitialized)
        
        Raises:
            ValueError: If item structure doesn't match loaded data format, or if
                       code_field is missing when lookup is uninitialized
        
        Example:
            >>> # Add to initialized lookup
            >>> lookup = LookUp()
            >>> lookup.load([{'code': 'ES', 'name': 'Spain'}], code_field='code')
            >>> lookup.add_item({'code': 'FR', 'name': 'France'})
            
            >>> # Add to uninitialized lookup (dict)
            >>> lookup2 = LookUp(code_format='upper')
            >>> lookup2.add_item({'country_code': 'es', 'name': 'Spain'}, code_field='country_code')
            
            >>> # Add to uninitialized lookup (list/tuple)
            >>> lookup3 = LookUp(code_format='upper')
            >>> lookup3.add_item(('fr', 'France', 'EUR'), code_field=0, headers=['code', 'country', 'currency'])
        
        Cost:
            O(1) for adding to primary index
            O(k) where k is the number of custom indices
        """
        # If lookup is not initialized, initialize it with first item
        if not self._loaded:
            if code_field is None:
                raise ValueError("code_field parameter is required when adding to uninitialized lookup")
            
            # Initialize with single item
            if isinstance(item, dict):
                self.load([item], code_field=code_field)
            else:
                self.load([item], code_field=code_field, headers=headers)
            return
        
        # Add to already initialized lookup
        if isinstance(item, dict):
            self._add_dict_item(item)
        else:
            self._add_list_item(item)
    
    def _add_dict_item(self, item_dict: Dict[str, Any]) -> None:
        """
        Add a single dictionary item to the cache.
        
        Args:
            item_dict: Dictionary representing the item
        """
        # Validate code field exists
        if self._code_field_name not in item_dict:
            raise ValueError(f"Code field '{self._code_field_name}' not found in item")
        
        # Extract and format code
        code_raw = item_dict[self._code_field_name]
        code_formatted = self._apply_format(code_raw, self._code_format)
        
        # Build formatted item dict
        formatted_item = {}
        for field_name in self._field_names:
            if field_name not in item_dict:
                formatted_item[field_name] = None
                continue
            
            if field_name == self._code_field_name:
                formatted_item[field_name] = code_formatted
            else:
                formatted_item[field_name] = item_dict[field_name]
        
        # Add to cache
        self._cache['data'].append(formatted_item)
        self._cache[self._code_field_name][code_formatted] = formatted_item
        
        # Index custom indexed fields
        for field_name, format_type in self._custom_indices.items():
            if field_name in formatted_item:
                field_value = formatted_item[field_name]
                field_value_formatted = self._apply_format(field_value, format_type)
                
                if field_name not in self._cache:
                    self._cache[field_name] = {}
                
                self._cache[field_name][field_value_formatted] = code_formatted

    def append(
        self,
        item: Union[Dict[str, Any], List[Any], Tuple[Any, ...]],
        code_field: Union[str, int, None] = None,
        headers: Optional[List[str]] = None
    ) -> None:
        """
        Append a single item to the existing cache (alias for add_item).
        
        Description:
            Adds one item to the cache using the current configuration.
            If the lookup is uninitialized, code_field is required.
        
        Args:
            item: Item to add (dict, list, or tuple)
            code_field: Primary index field (required if lookup is uninitialized)
            headers: Field names for list/tuple data (optional, only used if uninitialized)
        
        Raises:
            ValueError: If item structure doesn't match loaded data format, or if
                       code_field is missing when lookup is uninitialized
        
        Example:
            >>> # Append to initialized lookup
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain')], headers=['code', 'name'])
            >>> lookup.append(('FR', 'France'))
            
            >>> # Append to uninitialized lookup
            >>> lookup2 = LookUp()
            >>> lookup2.append(('ES', 'Spain'), code_field=0, headers=['code', 'name'])
        
        Cost:
            O(1) for adding to primary index
            O(k) where k is the number of custom indices
        """
        self.add_item(item, code_field=code_field, headers=headers)

    def get_item_by_code(
        self, 
        code: Any, 
        search_fn: Optional[Callable[[Any, str], Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve item dictionary by code.
        
        Description:
            Returns the complete item dictionary for the given code.
            Applies code formatting before search. Optionally accepts a custom
            search function for computationally optimized searches.
            
            The callable approach provides maximum flexibility for custom search
            strategies while maintaining O(1) performance when using the default
            dictionary-based search.
        
        Args:
            code: Code value to look up.
            search_fn: Optional callable for custom search strategy. 
                      Signature: (code: Any, formatted_code: str) -> Any
                      If provided, this function is called instead of the default
                      dictionary search. The function receives the original code
                      and the formatted code, and should return the item dict or None.
                      This allows for computationally efficient custom search strategies.
        
        Returns:
            Item dictionary or None if not found.
        
        Raises:
            TypeError: If search_fn is not callable.
        
        Computational Cost:
            O(1) for default dictionary search.
            Varies based on search_fn implementation when provided.
        
        Examples:
            >>> # Standard usage with default search
            >>> lookup = LookUp(code_format='upper')
            >>> lookup.load([('es', 'Spain', 'EUR')])
            >>> item = lookup.get_item_by_code('ES')
            >>> item['description']
            'Spain'
            
            >>> # Custom search with callable for optimized strategy
            >>> def custom_search(code, formatted_code):
            ...     # Custom efficient search logic
            ...     cache_dict = lookup._cache.get(lookup._code_field_name, {})
            ...     return cache_dict.get(formatted_code)
            >>> 
            >>> item = lookup.get_item_by_code('ES', search_fn=custom_search)
        """
        # Why: Validate that search_fn is callable if provided, preventing
        # runtime errors from invalid function arguments.
        if search_fn is not None and not callable(search_fn):
            raise TypeError(
                f"search_fn must be callable, got {type(search_fn).__name__}"
            )
        
        # Why: Apply formatting consistently before any search operation,
        # ensuring compatibility with the configured code_format.
        code_formatted = self._apply_format(code, self._code_format)
        
        # Why: Use custom search function if provided for computationally
        # efficient searches, otherwise fall back to default O(1) dict search.
        if search_fn is not None:
            return search_fn(code, code_formatted)
        
        # Why: Default dictionary-based search provides O(1) performance for
        # standard use cases without the overhead of function calls.
        return self._cache.get(self._code_field_name, {}).get(code_formatted)

    def create_index(self, field_name: str, format_type: Optional[str] = None) -> bool:
        """
        Create a dynamic index for fast lookups on a specific field.
        
        Description:
            Creates an O(1) lookup index for the specified field. All existing items
            will be indexed, and future items will be automatically indexed.
            Uses the format_type specified (or None for no formatting).
            Can be used to create an index for the 'description' field if needed.
        
        Args:
            field_name: Name of the field to index
            format_type: Optional format to apply ('upper', 'lower', 'capitalize', or None)
        
        Returns:
            True if index was created, False if field doesn't exist or index already exists
        
        Raises:
            ValueError: If format_type is invalid
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR')], headers=['code', 'country', 'currency'])
            >>> lookup.create_index('country', 'lower')  # Index description with format
            >>> lookup.get_code_by_index('country', 'spain')
            'ES'
            >>> lookup.create_index('currency')  # Index currency without format
            >>> lookup.get_code_by_index('currency', 'EUR')
            'ES'
        
        Cost:
            O(n) where n is the number of items in cache
        """
        # Validate format
        if format_type is not None:
            self._validate_format(format_type)
        
        # Check if field exists
        if field_name not in self._field_names:
            return False
        
        # Check if index already exists (use field name directly)
        if field_name in self._cache and field_name != 'data' and field_name != self._code_field_name:
            return False
        
        # Don't allow indexing the primary code field again
        if field_name == self._code_field_name:
            return False
        
        # Register custom index
        self._custom_indices[field_name] = format_type
        
        # Create index structure (use field name directly, not by_field_name)
        self._cache[field_name] = {}
        
        # Build index from existing data
        code_field = self._field_names[self._code_index]
        for item in self._cache['data']:
            if field_name in item:
                field_value = item[field_name]
                field_value_formatted = self._apply_format(field_value, format_type)
                code = item.get(code_field)
                
                if code is not None:
                    self._cache[field_name][field_value_formatted] = code
        
        return True

    def remove_index(self, field_name: str) -> bool:
        """
        Remove a dynamic index.
        
        Description:
            Removes the index for the specified field. Does not affect the primary
            index (code field) which is always maintained.
        
        Args:
            field_name: Name of the field index to remove
        
        Returns:
            True if index was removed, False if index doesn't exist
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR')], headers=['code', 'country', 'currency'])
            >>> lookup.create_index('currency')
            >>> lookup.remove_index('currency')
            True
        
        Cost:
            O(1)
        """
        # Don't allow removal of primary code index
        if field_name == self._code_field_name:
            return False
        
        # Check if index exists
        if field_name not in self._cache or field_name not in self._custom_indices:
            return False
        
        # Remove index
        del self._cache[field_name]
        del self._custom_indices[field_name]
        
        return True

    def get_code_by_index(self, field_name: str, field_value: Any) -> Optional[Any]:
        """
        Retrieve code by indexed field value.
        
        Description:
            Returns the code corresponding to the given field value using
            a previously created index. The field must have been indexed
            using create_index().
        
        Args:
            field_name: Name of the indexed field
            field_value: Value to look up in the specified field
        
        Returns:
            Code value or None if not found or field not indexed
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR')], headers=['code', 'country', 'currency'])
            >>> lookup.create_index('currency')
            >>> lookup.get_code_by_index('currency', 'EUR')
            'ES'
        
        Cost:
            O(1) if field is indexed, O(n) if not indexed
        """
        # Check if index exists (use field name directly)
        if field_name not in self._cache or field_name not in self._custom_indices:
            return None
        
        # Apply format if configured for this index
        format_type = self._custom_indices.get(field_name)
        field_value_formatted = self._apply_format(field_value, format_type)
        
        return self._cache[field_name].get(field_value_formatted)

    def get_indexed_fields(self) -> List[str]:
        """
        Get list of all indexed fields (excluding code and description).
        
        Description:
            Returns the names of all custom fields that have been indexed.
        
        Returns:
            List of custom indexed field names
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR', 'EU')], 
            ...             headers=['code', 'country', 'currency', 'zone'])
            >>> lookup.create_index('currency')
            >>> lookup.create_index('zone')
            >>> sorted(lookup.get_indexed_fields())
            ['currency', 'zone']
        
        Cost:
            O(n) where n is the number of custom indices
        """
        return list(self._custom_indices.keys())

    def is_field_indexed(self, field_name: str) -> bool:
        """
        Check if a field has been indexed.
        
        Description:
            Returns True if the specified field has a custom index created.
        
        Args:
            field_name: Name of the field to check
        
        Returns:
            True if field is indexed, False otherwise
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR')], headers=['code', 'country', 'currency'])
            >>> lookup.is_field_indexed('currency')
            False
            >>> lookup.create_index('currency')
            >>> lookup.is_field_indexed('currency')
            True
        
        Cost:
            O(1)
        """
        return field_name in self._custom_indices

    def get_code_by_field(self, field_name: str, field_value: Any) -> Optional[Any]:
        """
        Retrieve code by field value (legacy method, uses get_code_by_index).
        
        Description:
            This method is maintained for backward compatibility.
            If the field is indexed, uses O(1) lookup.
            If not indexed, performs O(n) linear search.
        
        Args:
            field_name: Name of the field to search
            field_value: Value to look up in the specified field
        
        Returns:
            Code value or None if not found
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR')], headers=['code', 'country', 'currency'])
            >>> lookup.create_index('currency')
            >>> lookup.get_code_by_field('currency', 'EUR')
            'ES'
        
        Cost:
            O(1) if field is indexed, O(n) if not indexed
        """
        # Try indexed lookup first
        result = self.get_code_by_index(field_name, field_value)
        if result is not None:
            return result
        
        # Fall back to linear search if not indexed
        code_field = self._field_names[self._code_index]
        
        for item in self._cache.get('data', []):
            if field_name in item:
                if item[field_name] == field_value:
                    return item.get(code_field)
        
        return None

    def get_all_items(self) -> List[Dict[str, Any]]:
        """
        Retrieve all items in the cache.
        
        Description:
            Returns a copy of the complete data list.
        
        Returns:
            List of all item dictionaries
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain'), ('FR', 'France')])
            >>> len(lookup.get_all_items())
            2
        
        Cost:
            O(n) where n is the number of items
        """
        return self._cache.get('data', []).copy()

    def get_all_codes(self) -> List[Any]:
        """
        Retrieve all codes in the cache.
        
        Description:
            Returns a list of all code values (formatted).
        
        Returns:
            List of all code values
        
        Example:
            >>> lookup = LookUp(code_format='upper')
            >>> lookup.load([('es', 'Spain'), ('fr', 'France')])
            >>> sorted(lookup.get_all_codes())
            ['ES', 'FR']
        
        Cost:
            O(n) where n is the number of items
        """
        return list(self._cache.get(self._code_field_name, {}).keys())

    def code_exists(self, code: Any) -> bool:
        """
        Check if a code exists in the cache.
        
        Description:
            Returns True if the given code is present in the cache.
        
        Args:
            code: Code value to check
        
        Returns:
            True if code exists, False otherwise
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain')])
            >>> lookup.code_exists('ES')
            True
            >>> lookup.code_exists('FR')
            False
        
        Cost:
            O(1)
        """
        code_formatted = self._apply_format(code, self._code_format)
        return code_formatted in self._cache.get(self._code_field_name, {})

    def remove(self, code: Any) -> bool:
        """
        Remove an item from the cache by code.
        
        Description:
            Removes the item with the specified code from all indices.
        
        Args:
            code: Code of the item to remove
        
        Returns:
            True if item was removed, False if not found
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain'), ('FR', 'France')])
            >>> lookup.remove('ES')
            True
            >>> lookup.code_exists('ES')
            False
        
        Cost:
            O(n + f) where n is cache size and f is number of fields
        """
        code_formatted = self._apply_format(code, self._code_format)
        
        # Get item before removing
        item = self._cache.get(self._code_field_name, {}).get(code_formatted)
        if not item:
            return False
        
        # Remove from primary index
        del self._cache[self._code_field_name][code_formatted]
        
        # Remove from custom field indices
        for field_name in self._custom_indices.keys():
            if field_name in self._cache and field_name in item:
                field_value = item[field_name]
                format_type = self._custom_indices.get(field_name)
                field_value_formatted = self._apply_format(field_value, format_type)
                
                if field_value_formatted in self._cache[field_name]:
                    del self._cache[field_name][field_value_formatted]
        
        # Remove from data list
        code_field = self._field_names[self._code_index]
        self._cache['data'] = [
            d for d in self._cache['data']
            if d.get(code_field) != code_formatted
        ]
        
        return True

    def clear(self) -> None:
        """
        Clear all data from the cache.
        
        Description:
            Removes all items and resets the cache to empty state.
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain')])
            >>> lookup.clear()
            >>> lookup.is_loaded()
            False
        
        Cost:
            O(1)
        """
        self._cache = {'data': []}
        self._field_names = []
        self._code_index = None
        self._code_field_name = None
        self._custom_indices = {}
        self._loaded = False

    def is_loaded(self) -> bool:
        """
        Check if data has been loaded.
        
        Description:
            Returns True if load() has been called successfully.
        
        Returns:
            True if data is loaded, False otherwise
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.is_loaded()
            False
            >>> lookup.load([('ES', 'Spain')])
            >>> lookup.is_loaded()
            True
        
        Cost:
            O(1)
        """
        return self._loaded

    def count(self) -> int:
        """
        Get the number of items in the cache.
        
        Description:
            Returns the total count of items loaded.
        
        Returns:
            Number of items in cache
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain'), ('FR', 'France')])
            >>> lookup.count()
            2
        
        Cost:
            O(1)
        """
        return len(self._cache.get('data', []))

    def get_field_names(self) -> List[str]:
        """
        Get the list of field names.
        
        Description:
            Returns the ordered list of field names in use.
        
        Returns:
            List of field names
        
        Example:
            >>> lookup = LookUp()
            >>> lookup.load([('ES', 'Spain', 'EUR')], headers=['code', 'country', 'currency'])
            >>> lookup.get_field_names()
            ['code', 'country', 'currency']
        
        Cost:
            O(1)
        """
        return self._field_names.copy()

    def __repr__(self) -> str:
        """
        String representation of the LookUp instance.
        
        Description:
            Provides a concise summary of the cache state.
        
        Returns:
            String representation
        
        Cost:
            O(1)
        """
        indexed_count = len(self._custom_indices)
        return (
            f"LookUp(items={self.count()}, "
            f"loaded={self.is_loaded()}, "
            f"code_format='{self._code_format}', "
            f"custom_indices={indexed_count})"
        )
