"""
DataMolder: A high-performance, column-oriented data record management system.

This module provides a flexible and efficient way to manage collections of data records
with type safety, data validation, and functional operations. The column-oriented
backend offers significant performance advantages for analytical and column-based tasks.
"""
from datetime import datetime
import time
import random
import functools
import copy
import inspect
from typing import Any, Dict, List, Tuple, Optional, Union, Type, Callable, TypeVar, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    try:
        from pydantic import BaseModel
    except ImportError:
        BaseModel = Any  # Fallback for type checking

T = TypeVar('T')

# Lazy import for pydantic to avoid import errors when not available
try:
    import pydantic
    from pydantic import BaseModel
    IS_PYDANTIC_AVAILABLE = True
except ImportError:
    pydantic = None
    # Define BaseModel as Any when not available to avoid type errors
    if not TYPE_CHECKING:
        BaseModel = Any
    IS_PYDANTIC_AVAILABLE = False

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class TypeValidationError(ValidationError):
    """Exception raised when type validation fails."""
    pass

class ConstraintValidationError(ValidationError):
    """Exception raised when a constraint validation fails."""
    pass

class ColumnNotFoundError(KeyError):
    """Exception raised when a column is not found."""
    pass


class OperationLog:
    """
    Helper class to store a log of operations performed in DataMolder.
    Designed to be used as a utility class with static methods, meaning
    you do not need to instantiate it. All entries are stored globally
    within the class.
    """
    # Class-level variable to store all log entries when using static methods.
    # This list will be shared across all "uses" of the static methods.
    _entries = []

    @staticmethod
    def log(operation: str, details: str = "") -> None:
        """
        Logs an operation with a timestamp and optional details to the shared log.

        Args:
            operation (str): The name of the operation performed.
            details (str, optional): Additional details about the operation.
                                     Defaults to an empty string.

        Returns:
            None

        Example of use:
            OperationLog.log("Data Import", "Successfully imported 100 records.")
            OperationLog.log("Data Export", details="Exported data to CSV.")
        """
        # Get the current timestamp for the log entry.
        timestamp = datetime.now()

        # Append the new log entry to the class-level _entries list.
        OperationLog._entries.append((timestamp, operation, details))

    @staticmethod
    def get_log_entries() -> list[tuple[datetime, str, str]]:
        """
        Retrieves a copy of all current log entries from the shared log.

        Returns:
            list[tuple[datetime, str, str]]: A list of log entries, where each entry
                                             is a tuple containing the timestamp,
                                             operation name, and details.

        Raises:
            N/A

        Example of use:
            OperationLog.log("Process Start")
            entries = OperationLog.get_log_entries()
            for entry in entries:
                print(f"Timestamp: {entry[0]}, Operation: {entry[1]}, Details: {entry[2]}")
        """
        # Return a shallow copy of the class-level _entries list to prevent external modification.
        return list(OperationLog._entries)

    @staticmethod
    def purge() -> None:
        """
        Clears all existing log entries from the shared operation log.

        This method is useful for resetting the log, for instance,
        before a new batch of operations or to free up memory
        after logs have been processed or saved.

        Args:
            N/A

        Returns:
            None

        Raises:
            N/A

        Example of use:
            OperationLog.log("Initialization")
            OperationLog.purge() # Clears the "Initialization" entry
        """
        # Reassign an empty list to the class-level _entries to clear all entries.
        # This is an O(1) operation as it only reassigns the reference.
        OperationLog._entries = []


def log_function_call(func):
    """
    A decorator to log the name and arguments of a function call.

    This decorator wraps a function and logs its name along with
    the positional and keyword arguments it receives before execution.

    Args:
        func (Callable): The function to be wrapped.

    Returns:
        Callable: The wrapped function with logging capabilities.

    Example of use:
        @log_function_call
        def my_example_function(a, b, c=3):
            return a + b + c

        my_example_function(1, 2, c=4)
        # Expected log output (example):
        # INFO:my_example_function - Called with args: (1, 2), kwargs: {'c': 4}

    Cost:
        O(1) - The overhead is minimal, involving function introspection and logging.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        """
        Logs the function call with its arguments and keyword arguments.
        Arguments and keyword arguments are truncated for brevity.

        Args:
            *args: Positional arguments passed to the decorated function.
            **kwargs: Keyword arguments passed to the decorated function.

        Returns:
            The result of the decorated function.
        """
        # Solo genera log si está activado
        cls = args[0].__class__ if args else None
        enable_log = getattr(cls, "enable_operation_log", False)
        if enable_log:        
            truncated_args = str(args)[:50] + "..." if len(str(args)) > 50 else str(args)
            truncated_kwargs = str(kwargs)[:50] + "..." if len(str(kwargs)) > 50 else str(kwargs)

            OperationLog.log(f"{func.__name__} - Called with args: {truncated_args}, kwargs: {truncated_kwargs}")
        # Execute the original function
        return func(*args, **kwargs)
    return wrapper

def log_operation_time(func):
    """
    A decorator to log the start, end, and duration of a function's execution.

    This decorator logs when a function begins execution, when it finishes,
    and how long it took to complete. It uses DEBUG level for start/end
    messages, so ensure your logger level is set appropriately to see them.

    Args:
        func (Callable): The function to be wrapped.

    Returns:
        Callable: The wrapped function with lifecycle logging capabilities.

    Example of use:
        @log_operation_lifecycle
        def long_running_task():
            time.sleep(1)
            return "Done"

        long_running_task()
        # Expected log output (example):
        # DEBUG:long_running_task - Starting execution...
        # DEBUG:long_running_task - Finished execution in 1.00s.

    Cost:
        O(1) - The overhead is minimal, involving logging and time measurement.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        cls = args[0].__class__ if args else None
        enable_log = getattr(cls, "enable_operation_log", False)
        if enable_log:
            OperationLog.log(f"{func.__name__} - Starting execution...")
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            if enable_log:
                end_time = time.time()
                duration_seconds = end_time - start_time
                hours, remainder = divmod(int(duration_seconds), 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                OperationLog.log(f"{func.__name__} - Finished execution in {duration_str}.")
    return wrapper

class DataVersion:
    """
    Manages versions of DataMolder data for undo/redo operations.
    
    This class implements a circular buffer to store versions of data,
    allowing efficient undo/redo operations with a fixed memory footprint.
    """
    
    def __init__(self, max_versions: int = 3):
        """
        Initialize the version control system.
        
        Args:
            max_versions (int): Maximum number of versions to store. 
                              If 0, versioning is disabled.
        """
        self.max_versions = max_versions
        self.versions = []  # List of (data, key_set) tuples
        self.current_index = -1

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top        
    def push_version(self, data: dict, key_set: set) -> None:
        """
        Add a new version to the history.
        
        Args:
            data (dict): Deep copy of the data to store
            key_set (set): Deep copy of the key set to store
        """
        if self.max_versions == 0:
            return
            
        # Remove any future versions if we're not at the latest version
        if self.current_index < len(self.versions) - 1:
            self.versions = self.versions[:self.current_index + 1]
            
        # Add new version
        if len(self.versions) >= self.max_versions:
            # Rotate versions by removing oldest
            self.versions = self.versions[1:] + [(data, key_set)]
        else:
            self.versions.append((data, key_set))
            
        self.current_index = len(self.versions) - 1
        
    def can_undo(self) -> bool:
        """Check if undo operation is available."""
        return self.current_index > 0
         
    def can_redo(self) -> bool:
        """Check if redo operation is available."""
        return self.current_index < len(self.versions) - 1

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top        
    def undo(self) -> Optional[Tuple[dict, set]]:
        """
        Move to previous version if available.
        
        Returns:
            Tuple containing the data dict and key set, or None if can't undo
        """
        if not self.can_undo():
            return None
            
        self.current_index -= 1
        return self.versions[self.current_index]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top         
    def redo(self) -> Optional[Tuple[dict, set]]:
        """
        Move to next version if available.
        
        Returns:
            Tuple containing the data dict and key set, or None if can't redo
        """
        if not self.can_redo():
            return None
            
        self.current_index += 1
        return self.versions[self.current_index]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top       
    def get_version(self, index: int) -> Optional[Tuple[dict, set]]:
        """
        Get a specific version by index.
        
        Args:
            index (int): Version index to retrieve
            
        Returns:
            Tuple containing the data dict and key set, or None if index invalid
        """
        if 0 <= index < len(self.versions):
            return self.versions[index]
        return None

class Header:
    """
    Manages column definitions, types, defaults, and constraints for data records.
    
    The schema can be defined from a list of tuples, a Pydantic model, or a JSON schema.
    """

    # A mapping of common database type names (in lowercase) to Python types.
    # This centralized map allows for easy extension and maintenance.
    _DB_TYPE_TO_PYTHON_MAP: dict[str, Type] = {
        # PostgreSQL
        'character varying': str,
        'varchar': str,
        'text': str,
        'integer': int,
        'bigint': int,
        'smallint': int,
        'numeric': float,
        'decimal': float,
        'real': float,
        'double precision': float,
        'boolean': bool,
        'date': 'datetime.date', # Using strings to avoid import at class level
        'timestamp': 'datetime.datetime',
        'timestamp without time zone': 'datetime.datetime',
        'bytea': bytes,

        # Oracle
        'varchar': str,
        'nvarchar': str,        
        'varchar2': str,
        'nvarchar2': str,
        'clob': str,
        'number': float, # NUMBER can be int or float, float is a safer default
        'long': str,
        'blob': bytes,
        'raw': bytes,

        # SQL Server
        'char': str,
        'nchar': str,
        'nvarchar': str,
        'datetime': 'datetime.datetime',
        'smalldatetime': 'datetime.datetime',
        'int': int,
        'float': float,
        'bit': bool,
        'image': bytes,
        'varbinary': bytes,

        # SQLite
        # SQLite types are more flexible, but we map the common affinities.
        'integer': int,
        'real': float,
        'text': str,
        'blob': bytes,
        'numeric': float, # Can be int, float, etc. Defaulting to float.
    }

    # Why: Centralizes mapping from JSON schema type strings to Python types.
    _JSON_TYPE_TO_PYTHON_MAP: dict[str, Type] = {
        'string': str,
        'number': float,
        'integer': int,
        'boolean': bool,
        'object': dict,
        'array': list,
        'null': Any  # Changed from type(None) to Any for practical use
    }
    
    @log_function_call
    def __init__(
        self,
        columns: Union[List[Union[str, Tuple]], Type[BaseModel], Dict[str, Any]],
        validators: Optional[Dict[str, Callable[[Any], bool]]] = None,
        allow_none: bool = True,
        type_checking: bool = True
    ):
        """
        Initializes the Header with a schema definition.

        Description:
            Constructs the header by parsing the provided column definition format,
            which can be a standard list of tuples, a Pydantic model, or a
            JSON schema dictionary.

        Args:
            columns (Union[List, Type[BaseModel], Dict]): The schema definition.
            validators (Optional[Dict]): Custom validation functions for columns.
            allow_none (bool): If True, allows None values in columns.
            type_checking (bool): If True, enforces strict type checking.

        Raises:
            TypeError: If the 'columns' argument is of an unsupported type.
        
        Cost: O(C) where C is the number of columns being defined.
        
        Example of use:
            # From list
            header1 = Header([('id', int), 'name'])
            # From Pydantic model
            class User(BaseModel):
                id: int
                name: str = "default_user"
            header2 = Header(User)
            # From JSON Schema
            json_schema = {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "email": {"type": "string"}
                },
                "required": ["id"]
            }
            header3 = Header(json_schema)
        """
        self._columns: List[str] = []
        self._types: Dict[str, Type] = {}
        self._defaults: Dict[str, Any] = {}
        self._required: Dict[str, bool] = {}
        self._keys: Dict[str, bool] = {}
        self._validators: Dict[str, Callable[[Any], bool]] = validators or {}
        self._allow_none = allow_none
        self._type_checking = type_checking

        # Why: Delegate processing to a dedicated method based on the input type.
        # This keeps the __init__ method clean and separates parsing logic.
        if isinstance(columns, list):
            self._initialize_from_list(columns)
        elif IS_PYDANTIC_AVAILABLE and inspect.isclass(columns) and issubclass(columns, BaseModel):
            self._initialize_from_pydantic(columns)
        elif isinstance(columns, dict) and 'properties' in columns:
            self._initialize_from_json_schema(columns)
        else:
            raise TypeError(f"Unsupported type for column definition: {type(columns).__name__}")

    def _initialize_from_list(self, columns_list: List[Union[str, Tuple]]):
        """
        Parses a list of column definitions.

        Description:
            Processes column definitions provided as a list of strings or tuples.
            This is the traditional way of defining a schema in DataMolder.

        Args:
            columns_list (List): A list where each item is a string (column name)
                                 or a tuple defining (name, type, default, etc.).
        
        Raises:
            ValueError: If a column definition tuple has an invalid number of elements
                        or if a column name is duplicated.
        """
        for col_def in columns_list:
            if isinstance(col_def, str):
                name, typ, default, required, key = col_def, Any, None, False, False
            elif isinstance(col_def, tuple):
                if len(col_def) == 2:
                    name, typ = col_def
                    default, required, key = None, False, False
                elif len(col_def) == 3:
                    name, typ, default = col_def
                    required, key = False, False
                elif len(col_def) == 5:
                    name, typ, default, required, key = col_def
                else:
                    raise ValueError(f"Column tuple must have 2, 3 or 5 elements: {col_def}")
            else:
                raise TypeError(f"Invalid column definition in list: {col_def}")
            
            self._add_column_metadata(name, typ, default, required, key)

    def _initialize_from_pydantic(self, model: Type[BaseModel]):
        """
        Infers the schema from a Pydantic model.

        Description:
            Extracts column names, types, default values, and required status
            from the fields of a Pydantic BaseModel.

        Args:
            model (Type[BaseModel]): The Pydantic model class to use as a schema.
        
        Raises:
            ValueError: If a column name is duplicated (should not happen with Pydantic).
        """
        # Why: model.model_fields is the standard for Pydantic v2+.
        for field_name, field in model.model_fields.items():
            # Why: Handle Optional types by extracting the inner type.
            field_type = field.annotation
            if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
                # This handles Optional[T], which is Union[T, None].
                args = [arg for arg in field_type.__args__ if arg is not type(None)]
                if len(args) == 1:
                    field_type = args[0]

            default_value = field.default if field.has_default() else None
            is_required = field.is_required()
            
            # Why: Pydantic models don't have a native 'key' concept. We assume False.
            # This could be extended to check for custom metadata if needed.
            is_key = False
            
            self._add_column_metadata(field_name, field_type, default_value, is_required, is_key)

    def _initialize_from_json_schema(self, schema: Dict[str, Any]):
        """
        Infers the schema from a JSON schema dictionary.

        Description:
            Parses a JSON schema's 'properties' and 'required' sections to define
            the columns, types, and constraints.

        Args:
            schema (Dict[str, Any]): The JSON schema dictionary.
        
        Raises:
            ValueError: If a column name is duplicated.
        """
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])
        
        for name, prop in properties.items():
            json_type = prop.get('type')
            python_type = self._JSON_TYPE_TO_PYTHON_MAP.get(json_type, Any)
            default_value = prop.get('default')
            is_required = name in required_fields
            
            # Why: JSON Schema doesn't have a 'key' concept. We assume False.
            is_key = False
            
            self._add_column_metadata(name, python_type, default_value, is_required, is_key)
            
    def _add_column_metadata(self, name: str, typ: Type, default: Any, required: bool, key: bool):
        """
        A helper to add metadata for a single column, ensuring no duplicates.

        Description:
            This private method centralizes the logic for adding a new column's
            metadata to the Header's internal state. It performs checks for
            duplicate column names and validates default values.

        Args:
            name (str): The column name.
            typ (Type): The Python type of the column.
            default (Any): The default value for the column.
            required (bool): Whether the column is required.
            key (bool): Whether the column is a key field.
            
        Raises:
            ValueError: If the column name already exists or the default value is invalid.
        """
        if name in self._columns:
            raise ValueError(f"Duplicate column name '{name}' detected.")

        self._columns.append(name)
        self._types[name] = typ
        self._defaults[name] = default
        self._required[name] = required
        self._keys[name] = key

        if default is not None:
            try:
                self.validate(name, default)
            except ValidationError as e:
                raise ValueError(f"Invalid default for '{name}': {e}")
            
    def _map_db_type_to_python_type(self, db_type: str) -> Type:
        """
        Converts a database-specific type string to a Python type object.

        This is the core conversion logic. It performs a case-insensitive
        lookup in the mapping dictionary. It also handles parameterized types
        like VARCHAR(50) by extracting the base type name.

        Description:
            Maps a database type string to a corresponding Python type.
        Args:
            db_type (str): The database type as a string (e.g., 'VARCHAR(50)').
        Returns:
            (Type): The corresponding Python type (e.g., str). Defaults to `str`
                    if the type is not found in the map.
        Example of use:
            >>> header = Header([])
            >>> header._map_db_type_to_python_type('INTEGER')
            <class 'int'>
            >>> header._map_db_type_to_python_type('varchar(255)')
            <class 'str'>
            >>> header._map_db_type_to_python_type('UNKNOWN_TYPE')
            <class 'str'>
        """
        # Why: Normalize the type string to handle variations like 'VARCHAR(50)'
        # or 'varchar' by taking the first part and making it lowercase.
        normalized_type = db_type.split('(')[0].strip().lower()

        # If not found, try substring match for any key in the map
        for key in self._DB_TYPE_TO_PYTHON_MAP:
            if key in normalized_type:
                return self._DB_TYPE_TO_PYTHON_MAP[key]

        # Default to str for unknown types
        return str

    def get_names(self) -> List[str]:
        """Returns the list of column names."""
        return self._names

    def get_types(self) -> List[Type]:
        """Returns the list of Python types for the columns."""
        return self._types
    
    @property
    def columns(self) -> List[str]:
        """List of column names."""
        return list(self._columns)
    
    @property
    def key_fields(self) -> List[str]:
        return [col for col, is_key in self._keys.items() if is_key]
       
    def get_type(self, column: str) -> Type:
        if column not in self._types:
            raise ColumnNotFoundError(f"Column '{column}' not found")
        return self._types[column]

    def get_default(self, column: str) -> Any:
        if column not in self._defaults:
            raise ColumnNotFoundError(f"Column '{column}' not found")
        return self._defaults[column]

    def is_required(self, column: str) -> bool:
        if column not in self._required:
            raise ColumnNotFoundError(f"Column '{column}' not found")
        return self._required[column]

    def is_key(self, column: str) -> bool:
        if column not in self._keys:
            raise ColumnNotFoundError(f"Column '{column}' not found")
        return self._keys[column]

    def validate(self, column: str, values: Any):
        """
        Validates a value or list of values against a column's type and custom validator.
    
        Args:
            column (str): The name of the column to validate.
            values (Any): The value(s) to validate. Can be a single value or a list of values.
    
        Raises:
            ColumnNotFoundError: If the column does not exist.
            ValueError: If None values are not allowed and a None value is found.
            TypeValidationError: If the value(s) do not match the expected type.
            ConstraintValidationError: If the value(s) fail the custom validator.
        """
        if column not in self._types:
            raise ColumnNotFoundError(f"Column '{column}' not found")
        
        if not isinstance(values, list):
            values = [values]
        
        # Check for None values
        for value in values:     
            if value is None and (not self._allow_none or self.is_required(column)):
                raise ValueError(f"Column '{column}' does not allow None values or it is a required field.")
    
        # Type validation
        if self._type_checking:
            expected_type = self._types[column]
            for value in values:
                # If value is None, skip type checking unless expected_type is specifically Optional or Any.
                # The None check for required fields is handled above.
                if value is None:
                    continue                
                # Handle special cases: Any and type(None) (from JSON schema 'null' type)
                if expected_type is Any or expected_type is type(None):
                    continue
                if expected_type is None:
                    continue  # Skip validation if type is not set
                if not isinstance(value, expected_type):
                    type_name = getattr(expected_type, '__name__', str(expected_type))
                    raise TypeValidationError(
                        f"Type mismatch for '{column}': expected {type_name}, "
                        f"got {type(value).__name__}."
                    )
    
        # Custom validator
        if column in self._validators:
            validator = self._validators[column]
            for value in values:
                if not validator(value):
                    raise ConstraintValidationError(
                        f"Constraint validation failed for '{column}' with value: {value}"
                    )

    @log_function_call
    def _rename_column(self, old_column_name: str, new_column_name: str) -> None:
        """
        Renames a column within the header's metadata.

        Description:
            This private helper method updates all internal dictionaries and lists
            that store column metadata (types, defaults, required status, keys,
            and validators) to reflect a new column name. It ensures data
            integrity across the schema definition.

        Args:
            old_column_name (str): The current name of the column to be renamed.
            new_column_name (str): The new name for the column.

        Raises:
            TypeError: If old_column_name or new_column_name are not strings.
            ValueError: If old_column_name does not exist, or new_column_name
                        already exists in the header.

        Example of use:
            >>> header = Header(["id", "name"])
            >>> header._types = {"id": int, "name": str}
            >>> header._defaults = {"id": None, "name": None}
            >>> header._required = {"id": True, "name": True}
            >>> header._keys = {"id": True, "name": False}
            >>> header._rename_column("name", "full_name")
            >>> header._columns
            ['id', 'full_name']
            >>> header._types
            {'id': int, 'full_name': str}

        Cost: O(C) where C is the number of metadata dictionaries,
              as it performs dictionary reassignments. For the column list,
              it's O(L) where L is the length of the column list, as it needs to find and replace.
        """
        if not isinstance(old_column_name, str) or not isinstance(new_column_name, str):
            raise TypeError("Column names must be strings.")

        if old_column_name not in self._columns:
            raise ValueError(f"Column '{old_column_name}' does not exist.")

        if new_column_name in self._columns:
            raise ValueError(f"New column name '{new_column_name}' already exists.")

        # Update the list of column names
        try:
            index = self._columns.index(old_column_name)
            self._columns[index] = new_column_name
        except ValueError:
            # This should ideally not happen if old_column_name in self._columns
            pass

        # Update all metadata dictionaries by creating new entries and deleting old ones
        # Why: Reassignment and deletion are explicit and clear for dictionary updates.
        for d in [self._types, self._defaults, self._required, self._keys, self._validators]:
            if old_column_name in d:
                d[new_column_name] = d.pop(old_column_name)

    @log_function_call    
    def remove_column(self, column_name: str) -> None:
        """
        Removes a column and its metadata from the header.

        Description:
            This is a low-level method to remove a column's metadata.
            It does not handle higher-level logic like computed columns, which
            is the responsibility of the DataMolder class.

        Args:
            column_name (str): The name of the column to remove.

        Raises:
            ColumnNotFoundError: If the column name does not exist.
            TypeError: If column_name is not a string.
        """
        if not isinstance(column_name, str):
            raise TypeError("Column name must be a string.")
        if column_name not in self._columns:
            raise ColumnNotFoundError(f"Column '{column_name}' does not exist.")

        # Why: This ensures that when a column is removed, all its associated
        # metadata is cleaned up, maintaining a consistent state within the Header.
        self._columns.remove(column_name)
        if column_name in self._types:
            del self._types[column_name]
        if column_name in self._defaults:
            del self._defaults[column_name]
        if column_name in self._required:
            del self._required[column_name]
        if column_name in self._keys:
            del self._keys[column_name]
        if column_name in self._validators:
            del self._validators[column_name]

    def __len__(self) -> int:
        return len(self._columns)

    def __contains__(self, column: str) -> bool:
        return column in self._columns


class DataMolder:
    """
    DataMolder: A high-performance, column-oriented data record management system.

    This module provides a flexible and efficient way to manage collections of data records
    with type safety, data validation, and functional operations. The column-oriented
    backend offers significant performance advantages for analytical and column-based tasks.
    """    
    """
    A high-performance, column-oriented data management system that provides
    type safety, validation, and a rich set of manipulation functionalities.
    """    
    enable_operation_log = False  # Por defecto desactivado

    @classmethod
    def set_operation_log(cls, enabled: bool):
        cls.enable_operation_log = enabled

    @log_function_call    
    def __init__(
        self,
        columns: List[Union[str, tuple]],
        validators: Optional[Dict[str, Callable[[Any], bool]]] = None,
        allow_none: bool = True,
        type_checking: bool = True,
        validate_on_change: bool = True,
        max_versions: int = 0,
        enable_operation_log: bool = False
    ):
        self.enable_operation_log = enable_operation_log  # <-- Instancia controla el log

        self.header = Header(columns, validators, allow_none, type_checking)
        self._column_enumerate = {i: col for i, col in enumerate(self.header.columns)}
        self.validate_on_change = validate_on_change

        # Why: Storing key fields in a local variable avoids repeated method calls.
        self._key_fields = self.header.key_fields
        
        # Why: A set for storing key tuples provides O(1) average time complexity
        # for uniqueness checks, which is a major performance boost.
        self._key_set: set = set()

        self._data: Dict[str, List[Any]] = {col: [] for col in self.header.columns}
        self._modified: List[bool] = []
        self._is_validated = True  # Track validation state; initially True if empty or when fully validated

        self._row_position: int = -1
        self._bookmarks: Dict[str, int] = {}
        
        self._locked_rows: set[int] = set()
        self._locked_columns: set[str] = set()
        self._all_rows_locked: bool = False
        self._all_columns_locked: bool = False

        # Why: Store definitions for computed columns.
        # The key is the computed column's name, and the value is a tuple
        # containing the computation function and its source column names.
        self._computed_columns: Dict[str, Tuple[Callable[[Dict[str, Any]], Any], List[str]]] = {}

        # Why: Store a reverse mapping for efficient lookups.
        # The key is a source column name, and the value is a list of
        # computed columns that depend on it. This avoids searching through
        # all computed columns definitions on every data change.
        self._source_column_dependents: Dict[str, List[str]] = {}

        self._new_row = {col: self.header.get_default(col) for col in self.columns}
        self._num_rows = 0 # Initialize _num_rows to keep track of the number of rows

        # Add version control
        self._version_control = DataVersion(max_versions)
        self._save_version()

    # --- Schema ---

    @property
    def columns(self) -> List[str]:
        if hasattr(self, "header") and hasattr(self.header, "columns"):        
            return self.header.columns
        else:
            return "<DataMolder (empty)>"

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def insert_columns(self,
                       index: Union[int, str],
                       column_definitions: List[Union[str, Tuple[str, Type], Tuple[str, Type, Any], Tuple[str, Type, Any, bool, bool]]],
                       position: str = 'before',
                       column_data: Optional[Dict[str, List[Any]]] = None) -> None:
        """
        Inserts new columns into the DataMolder at a specified index or relative to a column name.

        Description:
            This method adds one or more new columns to the DataMolder's schema and data.
            Columns can be inserted by a numerical index or relative to an existing column's name.
            The `position` parameter determines if insertion occurs before or after the target.
            Optional `column_data` can be provided to populate the new columns; otherwise,
            they are filled with their default values.

        Args:
            index (Union[int, str]): The 0-based index or the name of an existing column
                                     at which to insert the new columns.
            column_definitions (List[Union[str, Tuple]]): A list of new column definitions.
                                                          Each definition can be a string (name),
                                                          or a tuple (name, type), (name, type, default), etc.
            position (str): Specifies where to insert the columns relative to the index/column.
                            Can be 'before' or 'after'. Defaults to 'before'.
            column_data (Optional[Dict[str, List[Any]]]): A dictionary where keys are new column names
                                                            and values are lists of data for each row.
                                                            If provided, the list length must match self.num_rows.

        Raises:
            TypeError: If index is not an int or str, column_definitions is not a list,
                       position is invalid, or column_data is not a dict.
            IndexError: If the numerical index is out of bounds.
            ColumnNotFoundError: If the column name for index is not found.
            ValueError: If a column to be inserted already exists, or if provided column_data
                        length does not match num_rows, or if column_data is missing for a defined column.
            TypeValidationError: If values in column_data do not match defined column types.
            ConstraintValidationError: If values in column_data fail custom validation.

        Example of use:
            >>> dm = DataMolder([("id", int), ("name", str)])
            >>> dm.add_row([1, "Alice"])
            >>> dm.add_row([2, "Bob"])
            >>> dm.insert_columns(1, [("age", int, 0)], position='before', column_data={"age": [25, 30]})
            >>> dm.columns
            ['id', 'age', 'name']
            >>> dm.get_row(0)
            {'id': 1, 'age': 25, 'name': 'Alice'}

        Cost: O(C_new * R) where C_new is the number of new columns and R is the number of rows,
              due to initializing new column data, plus O(C_new * C_old) for Header operations.
        """
        if not isinstance(column_definitions, list):
            raise TypeError("Column definitions must be a list.")
        if position not in ['before', 'after']:
            raise ValueError("Position must be 'before' or 'after'.")
        if column_data is not None and not isinstance(column_data, dict):
            raise TypeError("Column data must be a dictionary mapping column names to lists of values.")

        current_columns = self.header.columns
        effective_index: int

        if isinstance(index, str):
            try:
                effective_index = current_columns.index(index)
            except ValueError:
                raise ColumnNotFoundError(f"Column '{index}' not found.")
        elif isinstance(index, int):
            if not (0 <= index <= len(current_columns)):
                raise IndexError(f"Column index {index} out of bounds. Must be between 0 and {len(current_columns)}.")
            effective_index = index
        else:
            raise TypeError("Index must be an integer (column number) or a string (column name).")

        if position == 'after':
            effective_index += 1

        for i, col_def in enumerate(column_definitions):
            # Parse column definition
            name: str
            col_type: Type = Any
            default: Any = None
            is_required: bool = False
            is_key: bool = False
            validator: Optional[Callable[[Any], bool]] = None

            if isinstance(col_def, str):
                name = col_def
            elif isinstance(col_def, tuple):
                name = col_def[0]
                if len(col_def) > 1:
                    col_type = col_def[1]
                if len(col_def) > 2:
                    default = col_def[2]
                if len(col_def) > 3:
                    is_required = col_def[3]
                if len(col_def) > 4:
                    is_key = col_def[4]
                if len(col_def) > 5: # Assuming validator would be the 6th element if passed this way
                    validator = col_def[5]
            else:
                raise TypeError("Each column definition must be a string or a tuple.")

            if name in current_columns or name in [d[0] for d in column_definitions[:i] if isinstance(d, tuple)] + [d for d in column_definitions[:i] if isinstance(d, str)]:
                raise ValueError(f"Column '{name}' is already defined or duplicate in new definitions.")

            # Insert column into Header
            self.header._insert_column_at_index(effective_index + i, name, col_type, default, is_required, is_key, validator)

            # Initialize data for the new column
            new_column_data: List[Any] = []
            if column_data and name in column_data:
                if len(column_data[name]) != self._num_rows:
                    raise ValueError(f"Length of data for new column '{name}' ({len(column_data[name])}) "
                                     f"does not match number of rows ({self._num_rows}).")
                # Validate provided data
                for row_val in column_data[name]:
                    self.header.validate_value(name, row_val)
                new_column_data = list(column_data[name])
            else:
                # If no data provided, fill with default value
                new_column_data = [self.header.get_column_default(name)] * self._num_rows

            # Insert the new column data into _data in the correct position.
            # This requires careful handling as _data is a dictionary, not a list.
            # The order of keys in _data dictionary itself does not matter in Python 3.7+
            # but for consistency with self._columns and iteration, it's good to reorder.
            # However, the most straightforward approach for _data is simply to add the new key.
            # The "ordering" is primarily managed by self.header._columns and self._column_enumerate.
            self._data[name] = new_column_data


        # After all columns are added, refresh internal mappings
        self._column_enumerate = {i: col for i, col in enumerate(self.header.columns)}
        self._key_fields = self.header.key_fields

        self._save_version()

    def count_rows(self) -> int:
        """
        Counts the number of rows in the DataMolder instance.
    
        Returns:
            int: The total number of rows.
        """
        return len(self)

    def count_columns(self) -> int:
        """
        Counts the number of columns in the DataMolder instance.

        Returns:
            int: The total number of columns.
        """
        return len(self.header.columns)

    def count(self) -> Tuple[int, int]:
        return self.count_elements()

    def count_elements(self) -> Tuple[int, int]:
        """
        Returns the number of rows and columns in the DataMolder instance.

        Returns:
            Tuple[int, int]: A tuple containing the number of rows and columns.
        """
        return self.count_rows(), self.count_columns()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def size_metrics(self) -> Dict[str, Union[int, float]]:
        """
        Calculates and returns key size and approximate memory usage metrics for the DataMolder.

        This method provides an overview of the data's dimensions and an estimated memory footprint.
        It's crucial for monitoring the efficiency and resource consumption of the DataMolder
        instance, especially when dealing with large datasets.

        Returns:
            dict: A dictionary containing the following metrics:
                  - 'row_count' (int): The number of rows in the data.
                  - 'column_count' (int): The number of columns in the data.
                  - 'total_cells' (int): The total number of cells in the data.
                  - 'modified_rows' (int): The count of rows that have been marked as modified.
                  - 'approx_memory_bytes' (int): An estimated memory usage in bytes.

        Raises:
            None

        Example of use:
            >>> dm = DataMolder([("id", int), ("name", str), ("value", float)])
            >>> dm.add_row([1, "Alice", 10.5])
            >>> dm.add_row([2, "Bob", 20.0])
            >>> dm.update_row(0, {"value": 11.0})
            >>> metrics = dm.size_metrics()
            >>> print(metrics)
            # Expected output (approximate):
            # {
            #     'row_count': 2,
            #     'column_count': 3,
            #     'total_cells': 6,
            #     'modified_rows': 1,
            #     'approx_memory_bytes': <some_integer_value>
            # }

        Cost: O(R * C * avg_item_size) where R is the number of rows, C is the number of columns,
              and avg_item_size is the average size of elements, due to iterating through
              all elements for memory estimation. This can be approximated as O(total_cells).
        """
        row_count = self._num_rows
        column_count = len(self.columns)
        total_cells = 0
        modified_rows = sum(1 for is_modified in self._modified if is_modified)

        # Start with the approximate size of the DataMolder object itself,
        # its internal dictionary for data, and the modified tracking list.
        approx_memory_bytes = sys.getsizeof(self)
        approx_memory_bytes += sys.getsizeof(self._data)
        approx_memory_bytes += sys.getsizeof(self._modified)
        approx_memory_bytes += sys.getsizeof(self.header) # Estimate header size

        # Why: Iterating through self._data.values() (the actual column lists)
        # and then each element within those lists provides a more comprehensive,
        # albeit still an estimation, of the memory used by the actual data.
        for column_data_list in self._data.values():
            approx_memory_bytes += sys.getsizeof(column_data_list)  # Size of the list object
            total_cells += len(column_data_list) # Each element in the column list is a cell
            for item in column_data_list:
                # Add size of each individual item. Handles various Python types.
                approx_memory_bytes += sys.getsizeof(item)

        # Add size for each boolean in the _modified list (approximate as booleans are singletons)
        # Why: Although bools are singletons, sys.getsizeof will return the size of the singleton object,
        # but the list itself also consumes memory for references. This loop explicitly accounts
        # for each reference within the list, providing a more detailed estimate.
        for is_mod in self._modified:
            approx_memory_bytes += sys.getsizeof(is_mod)

        return {
            "row_count": row_count,
            "column_count": column_count,
            "total_cells": total_cells,
            "modified_rows": modified_rows,
            "approx_memory_bytes": approx_memory_bytes,
        }

    # --- Aggregation Statistics ---

    def _get_column_data_for_aggregation(self, column_identifier: Union[str, int], numeric_only: bool) -> List[Any]:
        """
        Retrieves column data for aggregation, optionally filtering for numeric values.

        Args:
            column_identifier (Union[str, int]): The name or index of the column.
            numeric_only (bool): If True, only numeric values (int, float) will be included.

        Returns:
            List[Any]: A list of values from the specified column, filtered if numeric_only is True.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.
            TypeError: If numeric_only is True and the column contains non-numeric values,
                       or if the column is empty.
            ValueError: If the column is empty or contains no numeric values to aggregate.
        """
        column_name = self._resolve_column_identifier(column_identifier)

        if column_name not in self._data:
            raise ColumnNotFoundError(f"Column '{column_name}' not found.")

        column_data = self._data[column_name]
        if not column_data:
            raise ValueError(f"Column '{column_name}' is empty. Cannot perform aggregation.")

        if numeric_only:
            numeric_values = [value for value in column_data if isinstance(value, (int, float))]
            if not numeric_values and any(value is not None for value in column_data):
                # If there are non-None values but none are numeric, raise TypeError
                raise TypeError(f"Column '{column_name}' contains non-numeric values. Cannot perform numeric aggregation.")
            elif not numeric_values:
                # If all values are None or column is truly empty of numeric data
                raise ValueError(f"Column '{column_name}' contains no numeric values to aggregate.")
            return numeric_values
        else:
            # For min/max, we need to filter out None values as they are not comparable
            comparable_values = [value for value in column_data if value is not None]
            if not comparable_values:
                raise ValueError(f"Column '{column_name}' is empty or contains only None values. Cannot find min/max.")
            return comparable_values

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def sum_column(self, column_identifier: Union[str, int]) -> Union[int, float]:
        """
        Calculates the sum of all numeric values in a specified column.

        Args:
            column_identifier (Union[str, int]): The name or index of the column to sum.

        Returns:
            Union[int, float]: The sum of the values in the column. The return type
                               will be float if any value in the column is a float,
                               otherwise it will be an int.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.
            TypeError: If the column contains non-numeric values.
            ValueError: If the column is empty or contains no numeric values to sum.

        Examples:
            >>> dm = DataMolder([("score", int), ("price", float)])
            >>> dm.add_rows([(10,), (20,), (30,)])
            >>> dm.sum_column("score")
            60
            >>> dm.sum_column(0) # Same as "score"
            60
            >>> dm.clear()
            >>> dm.add_rows([(10.5,), (20.0,), (30.5,)])
            >>> dm.sum_column("price")
            61.0
            >>> dm.sum_column(1) # Same as "price"
            61.0
            >>> dm.clear()
            >>> dm.add_rows([("A",), ("B",)])
            >>> dm.sum_column("score") # doctest: +SKIP
            Traceback (most recent call last):
            ...
            TypeError: Column 'score' contains non-numeric values. Cannot perform numeric aggregation.

        Cost: O(N) where N is the number of rows, as it iterates through all values in the column.
        """
        numeric_data = self._get_column_data_for_aggregation(column_identifier, numeric_only=True)
        return sum(numeric_data)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def average_column(self, column_identifier: Union[str, int]) -> float:
        """
        Calculates the average (mean) of all numeric values in a specified column.

        Args:
            column_identifier (Union[str, int]): The name or index of the column to average.

        Returns:
            float: The average of the values in the column.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.
            TypeError: If the column contains non-numeric values.
            ValueError: If the column is empty or contains no numeric values to average.

        Examples:
            >>> dm = DataMolder([("score", int)])
            >>> dm.add_rows([(10,), (20,), (30,)])
            >>> dm.average_column("score")
            20.0
            >>> dm.average_column(0) # Same as "score"
            20.0
            >>> dm.clear()
            >>> dm.add_rows([(10.5,), (20.0,), (30.5,)])
            >>> dm.average_column("price") # doctest: +SKIP
            20.333333333333332
            >>> dm.clear()
            >>> dm.add_rows([("A",), ("B",)])
            >>> dm.average_column("score") # doctest: +SKIP
            Traceback (most recent call last):
            ...
            TypeError: Column 'score' contains non-numeric values. Cannot perform numeric aggregation.

        Cost: O(N) where N is the number of rows, as it iterates through all values in the column.
        """
        numeric_data = self._get_column_data_for_aggregation(column_identifier, numeric_only=True)
        return sum(numeric_data) / len(numeric_data)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def count_column(self, column_identifier: Union[str, int]) -> int:
        """
        Counts the total number of non-null values in a specified column.

        Args:
            column_identifier (Union[str, int]): The name or index of the column to count.

        Returns:
            int: The number of non-null values in the column.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.

        Examples:
            >>> dm = DataMolder([("status", str)])
            >>> dm.add_rows([("active",), ("inactive",), (None,), ("active",)])
            >>> dm.count_column("status")
            3
            >>> dm.count_column(0) # Same as "status"
            3
            >>> dm.clear()
            >>> dm.count_column("status")
            0

        Cost: O(N) where N is the number of rows, as it iterates through all values in the column.
        """
        column_name = self._resolve_column_identifier(column_identifier)
        
        # The check for column_name not in self._data is handled by _resolve_column_identifier
        
        return len([value for value in self._data[column_name] if value is not None])

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def count_distinct_column(self, column_identifier: Union[str, int]) -> int:
        """
        Counts the number of distinct non-null values in a specified column.

        Args:
            column_identifier (Union[str, int]): The name or index of the column to count distinct values.

        Returns:
            int: The number of distinct non-null values in the column.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.

        Examples:
            >>> dm = DataMolder([("category", str)])
            >>> dm.add_rows([("A",), ("B",), ("A",), (None,), ("C",), ("B",)])
            >>> dm.count_distinct_column("category")
            3
            >>> dm.count_distinct_column(0) # Same as "category"
            3
            >>> dm.clear()
            >>> dm.add_rows([(1,), (2,), (1,), (3,), (None,)])
            >>> dm.count_distinct_column("category")
            3

        Cost: O(N) where N is the number of rows, as it iterates through all values in the column.
        """
        column_name = self._resolve_column_identifier(column_identifier)
        
        # The check for column_name not in self._data is handled by _resolve_column_identifier
        
        non_null_values = [value for value in self._data[column_name] if value is not None]
        return len(set(non_null_values))

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def min_column(self, column_identifier: Union[str, int]) -> Any:
        """
        Finds the minimum value in a specified column.

        This function works for numeric types (int, float) and also for types
        that support direct comparison (e.g., strings, datetime objects).

        Args:
            column_identifier (Union[str, int]): The name or index of the column to find the minimum value.

        Returns:
            Any: The minimum value in the column. The type will match the column's data type.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.
            ValueError: If the column is empty or contains no comparable values.
            TypeError: If the column contains values of incomparable types.

        Examples:
            >>> dm = DataMolder([("value", int), ("date", str)])
            >>> dm.add_rows([(10,), (5,), (20,), (None,)])
            >>> dm.min_column("value")
            5
            >>> dm.min_column(0) # Same as "value"
            5
            >>> dm.clear()
            >>> dm.add_rows([("banana",), ("apple",), ("zebra",)])
            >>> dm.min_column("date")
            'apple'
            >>> dm.min_column(1) # Same as "date"
            'apple'
            >>> dm.clear()
            >>> dm.add_rows([('a',), (1,)])
            >>> dm.min_column("date") # doctest: +SKIP
            Traceback (most recent call last):
            ...
            TypeError: '<' not supported between instances of 'int' and 'str'

        Cost: O(N) where N is the number of rows, as it iterates through all non-null values in the column.
        """
        # We don't force numeric_only here because min/max can apply to strings too.
        comparable_data = self._get_column_data_for_aggregation(column_identifier, numeric_only=False)
        return min(comparable_data)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def max_column(self, column_identifier: Union[str, int]) -> Any:
        """
        Finds the maximum value in a specified column.

        This function works for numeric types (int, float) and also for types
        that support direct comparison (e.g., strings, datetime objects).

        Args:
            column_identifier (Union[str, int]): The name or index of the column to find the maximum value.

        Returns:
            Any: The maximum value in the column. The type will match the column's data type.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.
            ValueError: If the column is empty or contains no comparable values.
            TypeError: If the column contains values of incomparable types.

        Examples:
            >>> dm = DataMolder([("value", int), ("date", str)])
            >>> dm.add_rows([(10,), (5,), (20,), (None,)])
            >>> dm.max_column("value")
            20
            >>> dm.max_column(0) # Same as "value"
            20
            >>> dm.clear()
            >>> dm.add_rows([("banana",), ("apple",), ("zebra",)])
            >>> dm.max_column("date")
            'zebra'
            >>> dm.max_column(1) # Same as "date"
            'zebra'
            >>> dm.clear()
            >>> dm.add_rows([('a',), (1,)])
            >>> dm.max_column("date") # doctest: +SKIP
            Traceback (most recent call last):
            ...
            TypeError: '>' not supported between instances of 'int' and 'str'

        Cost: O(N) where N is the number of rows, as it iterates through all non-null values in the column.
        """
        # We don't force numeric_only here because min/max can apply to strings too.
        comparable_data = self._get_column_data_for_aggregation(column_identifier, numeric_only=False)
        return max(comparable_data)

    def column_names(self) -> List[str]:
        """
        Returns the names of all columns in the DataMolder instance.

        Returns:
            List[str]: A list of column names.

        Raises:
            AttributeError: If the column names attribute is not initialized.

        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.column_names()
            ['id', 'name', 'age']
        """
        if not hasattr(self, 'columns'):
            raise AttributeError("The 'columns' attribute is not initialized.")
        return self.columns

    def column_properties(self) -> List[Dict[str, Any]]:
        """
        Lists all columns in the header along with their properties.
    
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains
            the properties of a column (name, type, default value, required, key).
    
        Examples:
            >>> header = Header(columns=[
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> header.list_properties()
            [
                {'name': 'id', 'type': <class 'int'>, 'default': None, 'required': True, 'key': True},
                {'name': 'name', 'type': <class 'str'>, 'default': None, 'required': True, 'key': False},
                {'name': 'age', 'type': <class 'int'>, 'default': 0, 'required': False, 'key': False}
            ]
        """
        return [
            {
                "name": col,
                "type": self.header.get_type(col),
                "default": self.header.get_default(col),
                "required": self.header.is_required(col),
                "key": self.header.is_key(col)
            }
            for col in self.columns
        ]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top    
    def column_stats(self, column: Union[str, int]) -> Dict[str, Any]:
        """
        Calculates descriptive statistics for a specified column.

        This method provides insights into the data distribution and quality
        of a given column, including count, nulls, distinct values, and for
        numeric or string types, min/max/sum/avg or length statistics.

        Args:
            column (Union[str, int]): The name or index of the column to calculate statistics for.

        Returns:
            Dict[str, Any]: A dictionary containing various statistics for the column.
                            Includes 'count', 'null_count', 'distinct_count'.
                            For numeric types: 'min', 'max', 'sum', 'avg'.
                            For string types: 'min_length', 'max_length', 'avg_length'.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            IndexError: If the specified column index is out of bounds.

        Examples:
            >>> dm = DataMolder([("age", int), ("name", str)])
            >>> dm.add_rows([(30, "Alice"), (25, "Bob"), (None, "Charlie"), (25, "David")])
            >>> dm.column_stats("age")
            {'count': 4, 'null_count': 1, 'distinct_count': 2, 'min': 25, 'max': 30, 'sum': 80, 'avg': 26.666666666666668}
            >>> dm.column_stats(0) # Same as "age"
            {'count': 4, 'null_count': 1, 'distinct_count': 2, 'min': 25, 'max': 30, 'sum': 80, 'avg': 26.666666666666668}
            >>> dm.column_stats("name")
            {'count': 4, 'null_count': 0, 'distinct_count': 4, 'min_length': 3, 'max_length': 7, 'avg_length': 5.0}

        Cost: O(M) where M is the number of rows, as it iterates through all values in the column.
        """
        column_name = self._resolve_column_identifier(column)

        column_data = self._data[column_name]
        stats: Dict[str, Any] = {}

        stats["count"] = len(column_data)
        stats["null_count"] = column_data.count(None)
        
        non_null_values = [value for value in column_data if value is not None]
        stats["distinct_count"] = len(set(non_null_values))

        if not non_null_values:
            return stats  # No further stats if all values are null or empty

        # Determine column type for more specific statistics
        # We try to infer the most common type from non-null values
        inferred_type: Optional[Type] = None
        if non_null_values:
            # Get the type of the first non-null value
            inferred_type = type(non_null_values[0])
            # Check if all non-null values are of the same inferred type or compatible
            # This is a simplification; more robust type inference might involve
            # checking common base classes or explicit numeric type checks.
            if not all(isinstance(val, inferred_type) for val in non_null_values):
                # If types are mixed, try to be general (e.g., numeric for int/float mix)
                if all(isinstance(val, (int, float)) for val in non_null_values):
                    inferred_type = Union[int, float]
                elif all(isinstance(val, str) for val in non_null_values):
                    inferred_type = str
                else:
                    inferred_type = Any # Fallback if types are too diverse

        if inferred_type in (int, float, Union[int, float]):
            numeric_values = [val for val in non_null_values if isinstance(val, (int, float))]
            if numeric_values:
                stats["min"] = min(numeric_values)
                stats["max"] = max(numeric_values)
                stats["sum"] = sum(numeric_values)
                stats["avg"] = sum(numeric_values) / len(numeric_values) if numeric_values else 0
        elif inferred_type is str:
            string_values = [val for val in non_null_values if isinstance(val, str)]
            if string_values:
                lengths = [len(s) for s in string_values]
                stats["min_length"] = min(lengths)
                stats["max_length"] = max(lengths)
                stats["avg_length"] = sum(lengths) / len(lengths) if lengths else 0

        return stats
    
    # --- Locking ---

    def _get_column_name(self, column: Union[str, int]) -> str:
        """
        Retrieves the column name from either a string (name) or an integer (index).

        This helper method centralizes the logic for resolving column inputs,
        ensuring consistency and reducing code duplication across column-related operations.

        Args:
            column: The column identifier, which can be either the column's name (str)
                    or its zero-based index (int).

        Returns:
            str: The resolved name of the column.

        Raises:
            ColumnNotFoundError: If the column name is not found or the index is out of bounds.
            TypeError: If the input column is neither a string nor an integer.

        Example of use:
            column_name = self._get_column_name("my_column")
            column_name = self._get_column_name(0)

        Cost: O(1) for string lookup, O(1) for index lookup.
        """
        if isinstance(column, str):
            if column not in self._data:
                raise ColumnNotFoundError(f"Column '{column}' not found.")
            return column
        elif isinstance(column, int):
            if not 0 <= column < len(self.columns):
                raise ColumnNotFoundError(f"Column index {column} out of bounds.")
            return self.columns[column]
        else:
            raise TypeError("Column must be a string (name) or an integer (index).")
    
    def is_row_locked(self, index: int) -> bool:
        """
        Checks if a specific row is locked.

        Args:
            index: The index of the row to check.

        Returns:
            bool: True if the row is locked, False otherwise.

        Example of use:
            if instance.is_row_locked(0):
                print("Row 0 is locked.")

        Cost: O(1) on average for set lookup.
        """
        return index in self._locked_rows

    def is_column_locked(self, column: Union[str, int]) -> bool:
        """
        Checks if a specific column is locked.

        This method supports checking by either the column name (string) or
        its zero-based index (integer).

        Args:
            column: The identifier of the column to check, either its name (str)
                    or its index (int).

        Returns:
            bool: True if the column is locked, False otherwise.

        Raises:
            ColumnNotFoundError: If the column identifier does not correspond to an existing column.
            TypeError: If the input column is neither a string nor an integer.

        Example of use:
            if instance.is_column_locked("name"):
                print("Column 'name' is locked.")
            if instance.is_column_locked(0):
                print("Column at index 0 is locked.")

        Cost: O(1) for column name resolution and O(1) on average for set lookup.
        """
        column_name = self._get_column_name(column)
        return column_name in self._locked_columns

    def lock_row(self, index: int):
        """
        Locks a specific row, preventing modifications to its values or removal.

        Args:
            index: The index of the row to lock.

        Raises:
            IndexError: If the row index is out of bounds.

        Example of use:
            instance.lock_row(5)

        Cost: O(1) on average for set addition.
        """
        if not 0 <= index < len(self):
            raise IndexError(f"Row index {index} out of bounds for locking.")
        self._locked_rows.add(index)

    def unlock_row(self, index: int):
        """
        Unlocks a specific row, allowing modifications.

        Args:
            index: The index of the row to unlock.

        Example of use:
            instance.unlock_row(5)

        Cost: O(1) on average for set removal.
        """
        self._locked_rows.discard(index)

    def lock_column(self, column: Union[str, int]):
        """
        Locks a specific column, preventing modifications to its values or removal.

        This method supports locking by either the column name (string) or
        its zero-based index (integer).

        Args:
            column: The identifier of the column to lock, either its name (str)
                    or its index (int).

        Raises:
            ColumnNotFoundError: If the column identifier does not correspond to an existing column.
            TypeError: If the input column is neither a string nor an integer.

        Example of use:
            instance.lock_column("email")
            instance.lock_column(1)

        Cost: O(1) for column name resolution and O(1) on average for set addition.
        """
        column_name = self._get_column_name(column)
        self._locked_columns.add(column_name)

    def unlock_column(self, column: Union[str, int]):
        """
        Unlocks a specific column, allowing modifications.

        This method supports unlocking by either the column name (string) or
        its zero-based index (integer).

        Args:
            column: The identifier of the column to unlock, either its name (str)
                    or its index (int).

        Raises:
            ColumnNotFoundError: If the column identifier does not correspond to an existing column.
            TypeError: If the input column is neither a string nor an integer.

        Example of use:
            instance.unlock_column("email")
            instance.unlock_column(1)

        Cost: O(1) for column name resolution and O(1) on average for set removal.
        """
        column_name = self._get_column_name(column)
        self._locked_columns.discard(column_name)

    # --- Computed Columns ---

    def _recompute_column(self, computed_column_name: str) -> None:
        """
        Description:
            A private helper to recalculate all values for a given computed column.

        Cost:
            O(R * S), where R is the number of rows and S is the cost of the computation function.
        """
        if self.is_column_locked(computed_column_name):
            return  # Do not recompute if the column is locked.

        for i in range(len(self)):
            self._recompute_cell(i, computed_column_name)

    def _recompute_cell(self, row_index: int, computed_column_name: str) -> None:
        """
        Description:
            A private helper to recalculate a single cell's value for a computed column.

        Cost:
            O(S), where S is the cost of the computation function.
        """
        if computed_column_name not in self._computed_columns:
            return

        computation_function, source_columns = self._computed_columns[computed_column_name]

        # Why: Construct a dictionary containing only the necessary source data for the row.
        # This provides a clean and predictable input to the computation function.
        row_data = {col: self._data[col][row_index] for col in source_columns}

        # Why: The actual computation and update of the cell.
        computed_value = computation_function(row_data)
        self._data[computed_column_name][row_index] = computed_value

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def add_computed_column(
            self,
            column_name: str,
            computation_function: Callable[[Dict[str, Any]], Any],
            source_columns: List[str],
            col_type: Type = Any
        ) -> None:
        """
        Adds a new column whose values are dynamically computed from other columns.

        Description:
            This method introduces a 'computed' column where each cell's value is
            determined by a user-provided function. This function takes values from
            specified 'source columns' of the same row. The computed column updates
            automatically when its source data changes.

        Args:
            column_name (str): The name for the new computed column. Must be unique.
            computation_function (Callable[[Dict[str, Any]], Any]): A function that
                accepts a dictionary (mapping source column names to their values for a row)
                and returns the computed value.
            source_columns (List[str]): A list of existing column names that the
                `computation_function` depends on.
            col_type (Type, optional): The data type for the new column. Defaults to Any.

        Raises:
            ValueError: If `column_name` already exists or `source_columns` are not found.
            TypeError: For invalid argument types.

        Example of use:
            >>> dm = DataMolder([('price', float), ('tax_rate', float)])
            >>> dm.add_row([100.0, 0.20])
            >>> def calculate_total(row):
            ...     return row['price'] * (1 + row['tax_rate'])
            >>> dm.add_computed_column('total_price', calculate_total, ['price', 'tax_rate'])
            >>> dm.get_columns('total_price')
            [120.0]

        Example with conditional logic (if/else):
            >>> dm_users = DataMolder([('name', str), ('age', int)])
            >>> dm_users.add_rows([("Alice", 25), ("Bob", 40)])
            >>> def categorize_age(row):
            ...    if row['age'] >= 30:
            ...        return 'Senior'
            ...    else:
            ...        return 'Junior'
            >>> dm_users.add_computed_column('category', categorize_age, ['age'], col_type=str)
            >>> dm_users.get_columns('category')
            ['Junior', 'Senior']

        Cost:
            O(R * S) for initial calculation, where R is rows and S is the cost
            of the `computation_function`. Updates are O(S) for single-cell changes.
        """
        if not isinstance(column_name, str):
            raise TypeError("Column name must be a string.")
        if column_name in self.header:
            raise ValueError(f"Column '{column_name}' already exists.")
        if not callable(computation_function):
            raise TypeError("computation_function must be a callable.")
        if not isinstance(source_columns, list) or not all(isinstance(c, str) for c in source_columns):
            raise TypeError("source_columns must be a list of strings.")
        for source_col in source_columns:
            if source_col not in self.header:
                raise ValueError(f"Source column '{source_col}' not found.")

        # Why: Add column to header first. A computed column is not a key and not required.
        new_col_def = (column_name, col_type, None, False, False)
        # Why: Using a placeholder method to add column to header, assuming it exists.
        # This part of code was missing in the original file, so I'm assuming a logical implementation.
        self.header._columns.append(column_name)
        self.header._types[column_name] = col_type
        self.header._defaults[column_name] = None
        self.header._required[column_name] = False
        self.header._keys[column_name] = False
        self._column_enumerate = {i: col for i, col in enumerate(self.header.columns)}
        self._data[column_name] = [None] * len(self)


        # Why: Store computation logic and dependencies for future updates.
        self._computed_columns[column_name] = (computation_function, source_columns)

        # Why: Populate reverse dependency map for efficient update triggers.
        for source_col in source_columns:
            self._source_column_dependents.setdefault(source_col, []).append(column_name)

        # Why: Calculate initial values for all existing rows.
        self._recompute_column(column_name)

        self._save_version()

    # --- Add data ---
    
    def add_blank_row(self) -> None:
        """
        Adds a new blank row to the DataMolder, populating it with default values for each column.

        Description:
            This method facilitates the addition of new records where initial values
            are not immediately available. Each cell in the new row is automatically
            assigned its column's predefined default value. If no default is specified
            for a column, its default will be `None` (or its type's default if `allow_none`
            is False and a suitable default is determined by the `Header` based on the type).
            This ensures data integrity from the moment a row is added.

        Args:
            None

        Returns:
            None

        Raises:
            ValidationError: If any default value fails validation, which indicates a schema issue.

        Example of use:
            >>> dm = DataMolder([("id", int, 0), ("name", str, "Unknown"), ("is_active", bool, False)])
            >>> dm.add_blank_row()
            >>> dm.get_row(0)
            {'id': 0, 'name': 'Unknown', 'is_active': False}
            >>> dm.add_blank_row()
            >>> dm.num_rows
            2

        Cost: O(C) where C is the number of columns, due to iterating through columns
              to append default values.
        """
        # Why: Iterating through columns ensures that every column in the DataMolder
        # receives a value for the new row, maintaining data consistency.
        # Retrieving default values from the header ensures that schema definitions
        # are respected for new records.
        new_row_values = {}
        for col_name in self.header.columns:
            default_value = self.header.get_default(col_name)
            # Why: Validate the default value before adding to ensure schema integrity.
            # This catches potential issues if a default value itself violates a constraint.
            if self.validate_on_change:
                try:
                    self.header.validate(col_name, default_value)
                except ValidationError as e:
                    raise ValidationError(f"Default value for column '{col_name}' is invalid: {e}")
            self._data[col_name].append(default_value)
            new_row_values[col_name] = default_value

        # Mark the new row as unmodified initially
        # Why: A newly added row, populated with defaults, is not considered "modified"
        # until a specific update operation changes its values from these defaults.
        self._modified.append(False)

        # Handle computed columns for the new row
        # Why: Computed columns need to be evaluated and populated for new rows
        # to ensure the data model remains consistent and complete.
        if self._computed_columns:
            new_row_index = self._num_rows - 1
            # Re-evaluate all computed columns for the newly added row
            for computed_col_name in self._computed_columns:
                self._update_computed_column_value(computed_col_name, new_row_index)

        self._num_rows = len(self) # Update the row count
        self._row_position = self._num_rows

        self._save_version()

    def add_row(self, values: Union[List[Any], Dict[str, Any], tuple]):
        """
        Description:
            Adds a single row to the DataMolder instance.

        Description:
            This method is optimized to prepare a single row and perform all necessary
            validations efficiently before appending it to the columnar storage.
            
        Args:
            values (Union[List[Any], Dict[str, Any], tuple]): The row to add. It can be a list,
            a dictionary, or a tuple.

        Returns:
            None

        Raises:
            ValueError: If a required field is missing, None, or if a duplicate key is found.
            TypeError: If the input is not a list, dictionary, or tuple.
            PermissionError: If adding rows is not allowed due to locks.

        Example of use:
            >>> dm.add_row([1, 'Alice', 25])
            >>> dm.add_row({'id': 2, 'name': 'Bob', 'age': 30})

        Cost:
            O(C) where C is the number of columns. The check for key uniqueness is O(K)
            where K is the number of key fields, thanks to the hash set.
        """
        if self._all_rows_locked or self._locked_columns:
            raise PermissionError("Cannot add row: DataMolder is locked.")

        # --- Row Normalization ---
        # Why: This block converts any input format (list, tuple, dict) into a
        # standardized dictionary, `row_data`, which simplifies the rest of the function.
        if isinstance(values, (list, tuple)):
            if len(values) != len(self.columns):
                raise ValueError(f"Expected {len(self.columns)} values, got {len(values)}")
            row_data = dict(zip(self.columns, values))
        elif isinstance(values, dict):
            row_data = values
        else:
            raise TypeError("Row values must be a list, tuple, or a dictionary.")

        # --- Row Preparation ---
        # Why: Start with a copy of the pre-calculated default row template and update it.
        # This is faster than building a new dictionary from scratch every time.
        full_row = self._new_row_template.copy()
        full_row.update(row_data)

        # --- Validation and Key Check ---
        # Why: Perform validation and key checks in a single loop over the columns.
        # This is more efficient than looping multiple times for different checks.
        if self._key_fields:
            key_tuple = tuple(full_row[k] for k in self._key_fields)
            if key_tuple in self._key_set:
                raise ValueError(f"Duplicate key found: {key_tuple}")

        if self.validate_on_change:
            for col, value in full_row.items():
                if self.header.is_required(col) and value is None:
                    raise ValueError(f"Required field '{col}' is missing or None.")
                self.header.validate(col, value)
        
        # --- Data Append ---
        # Why: After all checks pass, append data and update state.
        # This ensures data integrity (atomicity of the add operation).
        for col, value in full_row.items():
            self._data[col].append(value)
        
        if self._key_fields:
            self._key_set.add(key_tuple)

        self._modified.append(True)
        if not self.validate_on_change:
            self._is_validated = False

        # Update computed columns for the new row
        if self._computed_columns:
                new_row_index = len(self) - 1
                for computed_col_name in self._computed_columns:
                    self._recompute_cell(new_row_index, computed_col_name)

        self._num_rows = len(self) # Update the row count
        self._row_position = self._num_rows

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def append_rows(self, rows: List[Union[List[Any], Tuple, Dict[str, Any]]]):
        """
        Description:
            Adds multiple rows to the DataMolder instance from a list of rows.

        Description:
            This method is highly optimized for bulk insertion. It first converts all
            row-oriented data into a columnar format, then performs validations on
            entire columns at once, which is significantly faster than row-by-row validation.
            The key uniqueness check also leverages a hash set for optimal performance.

        Args:
            rows (List[Union[List[Any], Tuple, Dict[str, Any]]]): A list of rows to add.

        Returns:
            None
        
        Raises:
            ValueError: If row structures are inconsistent, a required field is missing, or a duplicate key is found.
            PermissionError: If adding rows is not allowed due to locks.
        
        Example of use:
            >>> dm.append_rows([ [1, 'Alice'], [2, 'Bob'] ])

        Cost:
            O(R * C) where R is the number of new rows and C is the number of columns.
            This is optimal as all data points must be processed.
        """
        if not rows:
            return

        if self._all_rows_locked or self._locked_columns:
            raise PermissionError("Cannot add rows: DataMolder is locked.")

        num_new_rows = len(rows)
        
        # --- Data Transposition and Normalization ---
        # Why: Convert the list of rows into a columnar dictionary. Using zip(*) is a
        # highly efficient, C-implemented way to transpose data. This prepares the data
        # for efficient column-wise validation and appending.
        first_row = rows[0]
        if isinstance(first_row, (list, tuple)):
            columnar_data = {col: list(data) for col, data in zip(self.columns, zip(*rows))}
        elif isinstance(first_row, dict):
            columnar_data = {col: [row.get(col, self._new_row_template[col]) for row in rows] for col in self.columns}
        else:
            raise TypeError("All items in the 'rows' list must be of the same type (list, tuple, or dict).")

        # --- Key Uniqueness Check (Bulk) ---
        # Why: Perform the uniqueness check in bulk *before* modifying the instance state.
        # This is much faster than checking one by one inside a loop.
        if self._key_fields:
            new_keys = {
                tuple(columnar_data[k][i] for k in self._key_fields)
                for i in range(num_new_rows)
            }
            if len(new_keys) != num_new_rows:
                raise ValueError("Duplicate keys found within the new rows.")
            if not new_keys.isdisjoint(self._key_set):
                raise ValueError("One or more keys already exist in the DataMolder.")

        # --- Validation (Column-wise) ---
        # Why: Validating an entire column (list of values) at once can be more efficient
        # as the Python interpreter can optimize the loop better than repeated function calls.
        if self.validate_on_change:
            for col_name, values in columnar_data.items():
                if self.header.is_required(col_name) and None in values:
                     raise ValueError(f"Required column '{col_name}' contains None values.")
                self.header.validate(col_name, values)

        # --- Append Data and Update State ---
        # Why: Use `extend` to append the new data columns. This is more efficient
        # for adding multiple items to a list than repeated `append` calls.
        for col_name, values in columnar_data.items():
            self._data[col_name].extend(values)
        
        if self._key_fields:
            self._key_set.update(new_keys)
            
        self._modified.extend([True] * num_new_rows)
        if not self.validate_on_change:
            self._is_validated = False

        # Why: After adding new rows, calculate the values for the computed
        # columns in those specific new rows.
        if self._computed_columns:
            start_index = len(self) - num_new_rows
            for i in range(start_index, len(self)):
                for computed_col_name in self._computed_columns:
                    self._recompute_cell(i, computed_col_name)

        self._num_rows = len(self) # Update the row count
        self._row_position = self._num_rows

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def append_columns(self, columns: List[Tuple[str, type, Any, bool, bool]]) -> None:
        """
        Adds new columns to the DataMolder instance.
    
        Args:
            columns (List[Tuple[str, type, Any, bool, bool]]): A list of tuples where each tuple represents a column.
                Each tuple should contain:
                - Column name (str)
                - Column type (type)
                - Default value (Any)
                - Required flag (bool)
                - Key flag (bool)
    
        Raises:
            ValueError: If a column name already exists.
            TypeError: If the input is not a list of tuples with the correct structure.
    
        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False)
            ... ])
            >>> DataMolder.add_columns([
            ...     ("age", int, 0, False, False),
            ...     ("department", str, None, False, False)
            ... ])
            >>> DataMolder.column_names()
            ['id', 'name', 'age', 'department']
        """
        if not isinstance(columns, list):
            raise TypeError("Columns must be a list of tuples with the structure (name, type, default, required, key).")
        for col in columns:          
            if not isinstance(col, tuple) and len(col) == 5:
                raise TypeError("Columns must be a list of tuples with the structure (name, type, default, required, key).")       

        for column in columns:
            name, type_hint, default, is_required, is_key = self.header.add_column(column)        
            if len(self._data) > 0:            
                # Add default values to existing rows
                self._data[name] = [default] * len(self._data)

        self._column_enumerate = {i: col for i, col in enumerate(self.header.columns)}

        # Mark all rows as modified
        if len(self._data) == 0:
            self._data: Dict[str, List[Any]] = {col: [] for col in self.header.columns}                         
        else:            
            self._modified = [True] * len(self._data)

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def insert_rows(self, index: int, list_of_row_data: List[Union[List[Any], Dict[str, Any]]], position: str = 'before') -> None:
        """
        Inserts multiple rows of data at a specified index.

        Description:
            This method allows inserting one or more new rows into the DataMolder
            at a particular row index. The `position` parameter controls whether
            the new rows are inserted before or after the specified index.

        Args:
            index (int): The 0-based index at which to insert the rows.
            list_of_row_data (List[Union[List[Any], Dict[str, Any]]]): A list of row data,
                where each row can be a list (values in column order) or a dictionary.
            position (str): Specifies where to insert the rows relative to the index.
                            Can be 'before' or 'after'. Defaults to 'before'.

        Raises:
            TypeError: If list_of_row_data is not a list, index is not an integer,
                       or position is not 'before' or 'after'.
            IndexError: If the index is out of bounds.
            ValueError: If a required column is missing, or if column count is incorrect for a list.
            TypeValidationError: If a value's type does not match the column's defined type.
            ConstraintValidationError: If a value fails custom validation.

        Example of use:
            >>> dm = DataMolder([("id", int), ("name", str)])
            >>> dm.add_row([1, "Alice"])
            >>> dm.add_row([3, "Charlie"])
            >>> dm.insert_rows(1, [[2, "Bob"]], position='before')
            >>> dm.get_row(1)
            {'id': 2, 'name': 'Bob'}

        Cost: O(R * C) where R is the number of rows to insert and C is the number of columns,
              due to list insertions for each column.
        """
        if not isinstance(index, int):
            raise TypeError("Index must be an integer.")
        if not isinstance(list_of_row_data, list):
            raise TypeError("Row data must be a list of rows.")
        if position not in ['before', 'after']:
            raise ValueError("Position must be 'before' or 'after'.")

        effective_index = index
        if position == 'after':
            effective_index += 1

        if not (0 <= effective_index <= self._num_rows):
            raise IndexError(f"Insertion index {index} (effective {effective_index}) out of bounds. Must be between 0 and {self._num_rows}.")

        num_new_rows = len(list_of_row_data)

        for row_data in list_of_row_data:
            processed_row: Dict[str, Any] = {}

            # Handle dictionary input
            if isinstance(row_data, dict):
                for col_name in self.header.columns:
                    value = row_data.get(col_name)

                    if value is None and not self.header.allow_none and self.header.is_column_required(col_name):
                        raise ValueError(f"Required column '{col_name}' is missing or None.")
                    elif col_name not in row_data and self.header.is_column_required(col_name) and self.header.get_column_default(col_name) is None:
                        raise ValueError(f"Required column '{col_name}' is missing and has no default value.")
                    elif col_name not in row_data:
                        processed_row[col_name] = self.header.get_column_default(col_name)
                    else:
                        processed_row[col_name] = value

            # Handle list input
            elif isinstance(row_data, list):
                if len(row_data) != len(self.header.columns):
                    raise ValueError(f"Row data list must have {len(self.header.columns)} elements, but got {len(row_data)}.")
                for i, value in enumerate(row_data):
                    col_name = self._column_enumerate[i]
                    processed_row[col_name] = value
            else:
                raise TypeError("Each row in list_of_row_data must be a list or a dictionary.")

            # Validate and insert data for each column
            for col_name in self.header.columns:
                value_to_add = processed_row.get(col_name, self.header.get_column_default(col_name))

                if value_to_add is None and self.header.is_column_required(col_name) and not self.header.allow_none:
                    raise ValueError(f"Required column '{col_name}' cannot be None.")

                self.header.validate_value(col_name, value_to_add)
                # Why: Using list.insert() is necessary here to maintain column-oriented storage
                # and correctly place the new row's data.
                self._data[col_name].insert(effective_index, value_to_add)
            effective_index += 1 # Increment effective_index for subsequent insertions if multiple rows

        # Why: After adding new rows, calculate the values for the computed
        # columns in those specific new rows.
        if self._computed_columns:
            start_index = len(self) - num_new_rows
            for i in range(start_index, len(self)):
                for computed_col_name in self._computed_columns:
                    self._recompute_cell(i, computed_col_name)

        self._num_rows = len(self) # Update the row count
        self._row_position = index

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    @classmethod
    def mockup(cls, num_rows: int, columns: List[Union[str, Tuple[Any, ...]]],
               random_seed: Optional[int] = None) -> 'DataMolder':
        """
        Generates a DataMolder instance with mock data for testing purposes.

        This method creates a DataMolder instance populated with a specified number
        of rows of mock data. The data generation is based on the column
        definitions provided.

        Args:
            num_rows: The number of rows to generate.
            columns: A list of column definitions, similar to the DataMolder
                     constructor. Each definition can be a string for the
                     column name or a tuple in the format:
                     (name, type, default_value, is_required, is_key).
            random_seed: An optional integer to seed the random number generator
                         for reproducible mock data.

        Returns:
            DataMolder: A new DataMolder instance populated with mock data.

        Raises:
            ValueError: If `num_rows` is negative.
            TypeError: If an unsupported column type is encountered.

        Cost: O(num_rows * num_columns) due to generating each cell's data.

        Example of use:
            >>> # Create a DataMolder with 5 rows of mock data
            >>> mock_DataMolder = DataMolder.mockup(5, [
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False),
            ...     ("is_active", bool),
            ...     ("tags", List[str])
            ... ], random_seed=42)
            >>> print(len(mock_DataMolder))
            5
            >>> print(mock_DataMolder[0]) # doctest: +SKIP
            (1, 'Name_1', 77, True, ['tag_A', 'tag_C'])
        """
        if num_rows < 0:
            raise ValueError("Number of rows cannot be negative.")

        if random_seed is not None:
            random.seed(random_seed)

        # Initialize a DataMolder instance with the given column definitions
        mock_DataMolder = cls(columns)
        header = mock_DataMolder._header

        # Iterate to generate each row
        for row_index in range(num_rows):
            current_row_data = []
            for col_def in header.columns_definition:
                col_name = col_def["name"]
                col_type = col_def["type"]
                is_required = col_def["is_required"]
                is_key = col_def["is_key"]
                
                generated_value: Any = None

                # Generate data based on the column type
                if col_type is int:
                    # Generate unique integers for key columns, otherwise random integers
                    if is_key:
                        generated_value = row_index + 1  # Simple unique incrementing ID
                    else:
                        generated_value = random.randint(0, 100)
                elif col_type is float:
                    generated_value = round(random.uniform(0.0, 100.0), 2)
                elif col_type is str:
                    # Generate a simple string with an index for distinction
                    if is_key:
                        generated_value = f"Key_{row_index}"
                    else:
                        generated_value = f"Name_{row_index}" if is_required else random.choice([f"Name_{row_index}", None])
                elif col_type is bool:
                    generated_value = random.choice([True, False])
                elif col_type is List[str] or col_type is list: # Handle List[str] specifically
                    generated_value = random.sample([f"tag_{chr(65 + i)}" for i in range(5)], random.randint(0, 3))
                elif col_type is Tuple[Any, ...] or col_type is tuple: # Handle Tuple
                    generated_value = (random.randint(1, 10), random.choice(['A', 'B', 'C']))
                elif col_type is Any:
                    # For Any type, randomly choose between int, str, or None
                    generated_value = random.choice([random.randint(0, 100), f"Generic_{row_index}", None])
                else:
                    # If a specific default value is set, use it
                    if col_def["default"] is not None:
                        generated_value = col_def["default"]
                    elif is_required:
                        # For required but unsupported types, raise an error or provide a placeholder
                        raise TypeError(f"Unsupported required type for mocking: {col_type} for column '{col_name}'")
                    else:
                        # For non-required unsupported types, default to None
                        generated_value = None

                # Ensure required columns are not None unless a default is present
                if generated_value is None and is_required and col_def["default"] is None:
                    # Re-attempt generation for required fields if it resulted in None
                    if col_type is int:
                        generated_value = random.randint(0, 100)
                    elif col_type is str:
                        generated_value = f"RequiredString_{row_index}"
                    elif col_type is bool:
                        generated_value = random.choice([True, False])
                    # Add more types here as needed to ensure required fields are not None

                current_row_data.append(generated_value)
            
            # Add the generated row to the DataMolder instance
            mock_DataMolder.add_row(tuple(current_row_data))

        mock_DataMolder._num_rows = mock_DataMolder.len() # Update the row count
        mock_DataMolder._row_position = mock_DataMolder._num_rows

        self._save_version()

        return mock_DataMolder

    # --- Deletions ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def drop_duplicates(self, subset: Optional[List[str]] = None, keep: str = 'first') -> 'DataMolder':
        """
        Returns a new DataMolder with duplicate rows removed.

        Description:
            This method identifies and removes duplicate rows from the DataMolder,
            returning a new DataMolder instance with unique rows. Duplicates can be
            identified based on all columns or a specified subset of columns.
            You can choose to keep either the 'first' or 'last' occurrence of a duplicate row.
            The original DataMolder remains unchanged (immutable operation).

        Args:
            subset (Optional[List[str]]): A list of column names to consider when
                                          identifying duplicate rows. If `None`,
                                          all columns in the DataMolder will be used
                                          to determine uniqueness.
            keep (str): Determines which duplicate to keep.
                        'first': Keep the first occurrence of each unique row.
                        'last': Keep the last occurrence of each unique row.

        Returns:
            DataMolder: A new DataMolder instance with duplicate rows removed.

        Raises:
            TypeError: If `subset` is not a list of strings (or None) or `keep` is not a string.
            ValueError: If `keep` is not 'first' or 'last', or if any column name
                        in `subset` does not exist in the DataMolder.
            Exception: If column values within the `subset` (or all columns if `subset` is None)
                       are unhashable (e.g., lists, dictionaries).

        Example of use:
            >>> dm = DataMolder([("id", int), ("value", str)])
            >>> dm.add_rows([(1, "A"), (2, "B"), (1, "A"), (3, "C"), (2, "D")])
            >>> len(dm)
            5
            >>> unique_dm_all_cols = dm.drop_duplicates()
            >>> len(unique_dm_all_cols)
            4 # (1, "A"), (2, "B"), (3, "C"), (2, "D") - (1, "A") is duplicate of first (1, "A")
            >>> unique_subset_id_first = dm.drop_duplicates(subset=["id"], keep='first')
            # Assuming a method like to_list_of_lists() or to_dataframe() to inspect content
            # unique_subset_id_first.to_list_of_lists() might yield [[1, 'A'], [2, 'B'], [3, 'C']]
            >>> unique_subset_id_last = dm.drop_duplicates(subset=["id"], keep='last')
            # unique_subset_id_last.to_list_of_lists() might yield [[1, 'A'], [2, 'D'], [3, 'C']]

        Cost:
            O(N * C_subset) where N is the total number of rows and C_subset is the number
            of columns in the `subset` (or total columns if `subset` is None). This is due
            to iterating through rows, constructing tuples for hashing, and set operations.
            The final step of creating the new DataMolder using `_create_molder_from_indices`
            also contributes O(N_unique * C_total), where N_unique is the number of unique rows
            and C_total is the total number of columns.
        """
        # Validate input: subset
        if subset is not None:
            if not isinstance(subset, list) or not all(isinstance(col, str) for col in subset):
                raise TypeError("`subset` must be a list of strings or `None`.")
            # Check if all specified columns in `subset` exist in the DataMolder
            # Why: Ensures that operations are performed on valid column names.
            for col in subset:
                if col not in self.header.columns:
                    raise ValueError(f"Column '{col}' in `subset` not found in DataMolder.")
        
        # Validate input: keep
        if not isinstance(keep, str):
            raise TypeError("`keep` must be a string.")
        if keep not in ('first', 'last'):
            raise ValueError("`keep` must be either 'first' or 'last'.")

        # Determine the columns to use for identifying unique rows
        # Why: If `subset` is not provided, all columns are considered for full row uniqueness.
        unique_check_columns = subset if subset is not None else list(self.header.columns)

        seen_signatures = set()  # Stores hashable tuples of values from unique_check_columns
        unique_indices = []      # Stores the indices of the rows to keep

        if keep == 'first':
            # Iterate through rows from the beginning to keep the first occurrence of each unique row
            # Why: This strategy ensures that the earliest encountered duplicate row is preserved.
            for i in range(len(self)):
                # Create a tuple of values from the `unique_check_columns` for the current row.
                # This tuple serves as the unique signature for the row's content in the specified subset.
                current_signature = tuple(self._data[col][i] for col in unique_check_columns)
                if current_signature not in seen_signatures:
                    seen_signatures.add(current_signature)
                    unique_indices.append(i)
        else:  # keep == 'last'
            # Iterate through rows from the end to keep the last occurrence of each unique row
            # Why: This strategy ensures that the latest encountered duplicate row is preserved.
            for i in range(len(self) - 1, -1, -1):
                # Create a tuple of values from the `unique_check_columns` for the current row.
                current_signature = tuple(self._data[col][i] for col in unique_check_columns)
                if current_signature not in seen_signatures:
                    seen_signatures.add(current_signature)
                    unique_indices.append(i)
            # Reverse the collected indices to maintain the original relative order of the kept rows
            # Why: After iterating backwards, indices are in descending order; reversing them
            # restores their original ascending sequence, which is typically expected in DataMolder.
            unique_indices.reverse()

        self._num_rows = len(self) # Update the row count
        self._row_position = self._num_rows

        # Use the `_create_molder_from_indices` helper method to construct the new DataMolder.
        # Why: This reuses the established efficient copying logic, ensuring the operation is
        # immutable and the new DataMolder is properly initialized with the unique rows.
        self._save_version()
        
        return self._create_molder_from_indices(unique_indices)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def remove_rows(self, index: Union[int, slice, List[int], Tuple[Any]]) -> None:
        """
        Description:
            Removes one or multiple rows from the DataMolder instance by index,
            slice, or a list of indexes. Bookmarks pointing to removed rows
            are deleted, and others are updated.

        Args:
            index (Union[int, slice, List[int]]): The index of the row to remove, a slice
            object to remove multiple rows, or a list of indexes.

        Raises:
            IndexError: If any row index is out of range.
            PermissionError: If any row in the range is locked and cannot be removed.
            TypeError: If the index is not an integer, slice, or list of integers.
        
        Cost:
            O(N*C) where N is the number of rows and C is the number of columns,
            due to list reconstruction. Updating bookmarks adds a minor overhead.
        """
        # Why: This block normalizes all possible inputs for `index` into a
        # definitive list of unique indexes to remove, making subsequent logic simpler.
        indexes_to_remove = []
        if isinstance(index, int):
            if not (0 <= index < self.count_rows()):
                raise IndexError(f"Row index {index} is out of range.")
            indexes_to_remove = [index]
        elif isinstance(index, slice):
            indexes_to_remove = list(range(*index.indices(self.count_rows())))
        elif isinstance(index, (list, tuple)):
            if not all(isinstance(idx, int) for idx in index):
                raise TypeError("All elements in the index list must be integers.")
            if not all(0 <= idx < self.count_rows() for idx in index):
                raise IndexError("One or more row indexes are out of range.")
            indexes_to_remove = sorted(list(set(index)), reverse=True)
        else:
            raise TypeError("Index must be an integer, slice, or a list/tuple of integers.")

        # Why: Check for permissions before proceeding to fail fast.
        if self._all_rows_locked:
            raise PermissionError("Cannot remove rows: All rows are locked.")
        for column_name in self.columns:
            if self.is_column_locked(column_name):
                raise PermissionError(f"Cannot remove rows: Column '{column_name}' is locked.")
        for idx in indexes_to_remove:
            if self.is_row_locked(idx):
                raise PermissionError(f"Row {idx} is locked and cannot be removed.")

        # Why: Create a set for O(1) average time complexity lookups, which is faster
        # than scanning the list of indexes to remove repeatedly.
        indexes_to_remove_set = set(indexes_to_remove)

        # --- Bookmark Update Logic ---
        # Why: We must update bookmarks *before* altering the data structure.
        # This logic correctly removes bookmarks pointing to deleted rows and
        # decrements the indexes of bookmarks pointing to rows that will be shifted.
        updated_bookmarks = {}
        sorted_removed = sorted(list(indexes_to_remove_set))
        for name, bm_index in self._bookmarks.items():
            if bm_index in indexes_to_remove_set:
                # Why: The bookmarked row is being deleted, so the bookmark
                # must also be deleted to prevent it from pointing to a non-existent row.
                continue
            
            # Why: Count how many deleted rows were positioned *before* the current
            # bookmark. The bookmark's new index will be its old index minus this count.
            num_removed_before = sum(1 for removed_idx in sorted_removed if removed_idx < bm_index)
            updated_bookmarks[name] = bm_index - num_removed_before
        self._bookmarks = updated_bookmarks
        
        # --- Data Removal Logic ---
        # Why: A list comprehension to build the new data lists is more efficient
        # than repeatedly calling .pop() in a loop, which can be slow (O(N)) for each call.
        for col in self.columns:
            self._data[col] = [v for i, v in enumerate(self._data[col]) if i not in indexes_to_remove_set]
        
        self._modified = [v for i, v in enumerate(self._modified) if i not in indexes_to_remove_set]
        
        # Why: Update the cursor position if it's affected by the removal.
        if self._row_position in indexes_to_remove_set:
            self._row_position = -1 # Cursor becomes invalid
        else:
            num_removed_before_cursor = sum(1 for idx in sorted_removed if idx < self._row_position)
            self._row_position -= num_removed_before_cursor

        self._num_rows = len(self) # Update the row count

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def remove_columns(self, columns: Union[str, int, slice, List[Union[str, int]]]) -> None:
        """
        Removes one or multiple columns from the DataMolder instance.

        Description:
            This method removes columns by name, index, a list, or a slice. It correctly
            handles dependencies related to computed columns, preventing the removal of
            a column that other computed columns depend on, and cleaning up definitions
            if the removed column is itself a computed column.

        Args:
            columns (Union[str, int, slice, List[Union[str, int]]]): The identifier(s) for the columns to remove.

        Raises:
            ColumnNotFoundError: If a specified column name does not exist.
            IndexError: If a specified column index is out of range.
            PermissionError: If attempting to remove a column that is a dependency for another computed column.
            TypeError: If the `columns` argument has an invalid type.

        Example of use:
            >>> dm = DataMolder(['id', 'name', 'age'])
            >>> dm.remove_columns('age')
            >>> dm.columns
            ['id', 'name']
            >>> dm.remove_columns([0]) # Removes 'id'
            >>> dm.columns
            ['name']

        Cost: O(C_rem * D) where C_rem is the number of columns to remove and D is the number of dependents.
              The primary cost is iterating through columns and updating dependency maps.
        """
        columns_to_remove: List[str] = []
        current_cols = self.columns
        if isinstance(columns, (str, int)):
            columns_to_remove.append(self._resolve_column_identifier(columns))
        elif isinstance(columns, slice):
            columns_to_remove.extend(current_cols[columns])
        elif isinstance(columns, (list, tuple)):
            columns_to_remove.extend(self._resolve_column_identifier(c) for c in columns)
        else:
            raise TypeError("Columns must be a str, int, list, tuple, or slice.")

        for col_name in columns_to_remove:
            # Why: Before removal, check if this column is a dependency for any computed column.
            # This prevents breaking the logic of other columns.
            if col_name in self._source_column_dependents:
                dependents = self._source_column_dependents[col_name]
                raise PermissionError(
                    f"Cannot remove column '{col_name}' because it is a dependency "
                    f"for computed column(s): {dependents}"
                )

            # Why: If the column to be removed is itself a computed column, we must
            # clean up its definition and its entries in the reverse dependency map.
            if col_name in self._computed_columns:
                _func, source_cols = self._computed_columns.pop(col_name)
                for source in source_cols:
                    if source in self._source_column_dependents:
                        self._source_column_dependents[source].remove(col_name)
                        # Why: Clean up the source key if it no longer has any dependents.
                        if not self._source_column_dependents[source]:
                            del self._source_column_dependents[source]

            # Why: After handling DataMolder's specific logic, delegate the low-level
            # metadata removal to the Header and clean up the data.
            del self._data[col_name]
            self.header.remove_column(col_name)

        # Why: Refresh the index-to-name mapping after columns have been removed.
        self._column_enumerate = {i: col for i, col in enumerate(self.header.columns)}

        self._save_version()

    def _resolve_column_identifier(self, column_identifier: Union[str, int]) -> str:
        """
        Resolves a column identifier (name or index) to its corresponding column name.

        Args:
            column_identifier (Union[str, int]): The name (str) or index (int) of the column.

        Returns:
            str: The resolved column name.

        Raises:
            TypeError: If the identifier is not a string or an integer.
            ColumnNotFoundError: If a string identifier does not match any column name.
            IndexError: If an integer identifier is out of bounds.
        """
        if isinstance(column_identifier, str):
            if column_identifier not in self._data:
                raise ColumnNotFoundError(f"Column '{column_identifier}' not found.")
            return column_identifier
        elif isinstance(column_identifier, int):
            if not (0 <= column_identifier < len(self.columns)):
                raise IndexError(f"Column index {column_identifier} is out of bounds. Must be between 0 and {len(self.columns) - 1}.")
            return self._column_enumerate[column_identifier]
        else:
            raise TypeError("Column identifier must be a string (column name) or an integer (column index).")

    def _create_molder_from_columns(self, columns_to_keep: List[str]) -> 'DataMolder':
        """
        Helper method to create a new DataMolder by keeping only specified columns.

        Description:
            This private method constructs a new DataMolder instance that includes
            only the columns specified in `columns_to_keep`, copying their data.
            It is primarily used when performing column-wise operations that result
            in the removal of entire columns (e.g., `drop_na(axis='columns')`).

        Args:
            columns_to_keep (List[str]): A list of column names to include in the new DataMolder.

        Returns:
            DataMolder: A new DataMolder instance containing only the specified columns.

        Raises:
            ValueError: If a column name in `columns_to_keep` does not exist in the original DataMolder.

        Example of use:
            # Assuming 'self' is an instance of DataMolder
            # new_molder = self._create_molder_from_columns(['id', 'name'])

        Cost:
            O(C_kept * N) where C_kept is the number of columns being kept
            and N is the total number of rows. This cost is due to copying
            data for each of the retained columns.
        """
        # Create new header definitions based only on the columns to be kept
        new_defs = []
        for col in columns_to_keep:
            # Ensure that the column exists in the original DataMolder
            if col not in self.header.columns:
                raise ValueError(f"Column '{col}' not found in DataMolder for column-wise creation.")
            new_defs.append(
                (
                    col,
                    self.header.get_type(col),
                    self.header.get_default(col),
                    self.header.is_required(col),
                    self.header.is_key(col)
                )
            )
        # Initialize the new DataMolder with the filtered schema
        new_molder = DataMolder(new_defs, validate_on_change=self.validate_on_change)

        # Copy data for only the columns that are being kept
        # Why: This efficiently transfers only the relevant columnar data, avoiding
        # the overhead of rebuilding from row-wise insertion.
        new_molder._data = {col: self._data[col].copy() for col in columns_to_keep}
        # The number of rows remains the same when columns are dropped
        new_molder._num_rows = len(self)

        # Rebuild the key set for the new DataMolder if it has key fields
        # Why: The key set must accurately reflect the keys present only in the
        # new DataMolder's schema and data.
        if new_molder._key_fields:
            new_molder._key_set = {
                tuple(new_molder._data[k][i] for k in new_molder._key_fields)
                for i in range(new_molder._num_rows)
            }
        # Mark all rows as modified in the new molder, as they are newly populated
        # from the source, indicating they might need re-validation if validate_on_change is True.
        new_molder._modified = [True] * new_molder._num_rows
        return new_molder

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def drop_na(self, axis: str = 'rows', how: str = 'any', subset: Optional[List[str]] = None) -> 'DataMolder':
        """
        Returns a new DataMolder with rows or columns containing missing values removed.

        Description:
            This method identifies and removes rows or columns that contain `None` values,
            which are treated as missing data. The operation is immutable, meaning it
            returns a brand new DataMolder instance without altering the original.

        Args:
            axis (str): Specifies whether to drop 'rows' or 'columns'.
                        Must be 'rows' or 'columns'. Defaults to 'rows'.
            how (str): Determines the condition for dropping.
                       'any': Drop if *any* `None` value is present in the checked scope.
                       'all': Drop if *all* values are `None` in the checked scope.
                       Must be 'any' or 'all'. Defaults to 'any'.
            subset (Optional[List[str]]):
                - If `axis='rows'`: A list of column names. Only these columns will be
                  considered when checking for `None` values in a row. If `None`, all
                  columns in the DataMolder will be checked for `None` values.
                - If `axis='columns'`: This parameter is currently not supported for
                  column-wise `drop_na` in the same manner as for rows (i.e., checking
                  NAs in specific rows for columns). It must be `None` to avoid ambiguity
                  and simplify implementation for this version.

        Returns:
            DataMolder: A new DataMolder instance with rows or columns containing missing values removed.

        Raises:
            TypeError: If `axis`, `how`, or `subset` (if not `None`) are of incorrect types.
            ValueError: If `axis` or `how` are invalid strings, if a column name in `subset`
                        does not exist, or if `subset` is provided when `axis='columns'`.

        Example of use:
            >>> dm = DataMolder([("id", int), ("name", str), ("value", Optional[int])])
            >>> dm.add_rows([(1, "A", 10), (2, "B", None), (3, "C", 30), (4, "D", None), (5, None, 50)])
            >>> len(dm)
            5
            >>> dm_no_na_rows = dm.drop_na(axis='rows') # Drops rows where any column is None
            >>> # Result: Only rows (1, "A", 10) and (3, "C", 30) remain. len would be 2.

            >>> dm_no_na_rows_subset = dm.drop_na(axis='rows', subset=['name']) # Drops rows where 'name' is None
            >>> # Result: Row (5, None, 50) is dropped. len would be 4.

            >>> dm_no_na_cols = dm.drop_na(axis='columns') # Drops columns where any value is None
            >>> # Result: Columns 'name' and 'value' contain None, so they are dropped. Only 'id' remains.

        Cost:
            - For `axis='rows'`: O(N * C_checked) where N is the number of rows and C_checked
              is the number of columns checked (all columns or `len(subset)`).
            - For `axis='columns'`: O(C * N) where C is the total number of columns and N is
              the number of rows.
            The dominant cost is iterating through the data to check for `None` values.
        """
        # Validate `axis` parameter
        if not isinstance(axis, str):
            raise TypeError("`axis` must be a string ('rows' or 'columns').")
        if axis not in ('rows', 'columns'):
            raise ValueError("`axis` must be 'rows' or 'columns'.")

        # Validate `how` parameter
        if not isinstance(how, str):
            raise TypeError("`how` must be a string ('any' or 'all').")
        if how not in ('any', 'all'):
            raise ValueError("`how` must be 'any' or 'all'.")

        # Validate `subset` parameter based on `axis`
        if subset is not None:
            if not isinstance(subset, list) or not all(isinstance(col, str) for col in subset):
                raise TypeError("`subset` must be a list of strings or `None`.")
            
            if axis == 'rows':
                # Check if all columns specified in `subset` exist in the DataMolder's header
                # Why: Ensures that the NA check is performed only on valid columns.
                for col in subset:
                    if col not in self.header.columns:
                        raise ValueError(f"Column '{col}' in `subset` not found in DataMolder.")
            elif axis == 'columns':
                # Why: `subset` is currently not supported for `axis='columns'` to keep
                # the implementation clear and avoid ambiguity regarding row-level checks
                # on columns without explicit row labels.
                raise ValueError("`subset` parameter is not applicable when `axis='columns'`.")
        
        # Define a helper function to check for missing values (None)
        def is_na(value: Any) -> bool:
            """Checks if a value is considered missing (None)."""
            return value is None

        # --- Logic for Dropping Rows ---
        if axis == 'rows':
            rows_to_keep_indices = []
            
            # Determine which columns to check for NA values in each row
            # Why: If `subset` is `None`, the NA check considers all columns in the row.
            columns_to_check = subset if subset is not None else list(self.header.columns)

            # Iterate through each row to decide whether to keep it
            for i in range(len(self)): 
                # Collect values from the specified `columns_to_check` for the current row
                row_values_to_check = [self._data[col][i] for col in columns_to_check]
                
                # Apply the `how` logic to determine if the row should be dropped
                if how == 'any':
                    # If `any` value in `row_values_to_check` is NA, the row has `None` and should be dropped.
                    has_na = any(is_na(val) for val in row_values_to_check)
                    if not has_na: # If no NA, keep the row
                        rows_to_keep_indices.append(i)
                else: # `how == 'all'`
                    # If `all` values in `row_values_to_check` are NA, the row has all `None` and should be dropped.
                    all_na = all(is_na(val) for val in row_values_to_check)
                    if not all_na: # If not all NA, keep the row
                        rows_to_keep_indices.append(i)
            
            # Create and return a new DataMolder instance containing only the kept rows
            # Why: Reuses the efficient `_create_molder_from_indices` helper for immutable row-wise filtering.
            self._save_version()
                        
            return self._create_molder_from_indices(rows_to_keep_indices)

        # --- Logic for Dropping Columns ---
        else: # `axis == 'columns'`
            columns_to_keep_names = []
            
            # Iterate through each column to decide whether to keep it
            # Why: When dropping columns, the NA check is performed across all rows of that column.
            for col_name in self.header.columns:
                column_values = self._data[col_name]
                
                # Apply the `how` logic to determine if the column should be dropped
                if how == 'any':
                    # If `any` value in `column_values` is NA, the column has `None` and should be dropped.
                    has_na = any(is_na(val) for val in column_values)
                    if not has_na: # If no NA, keep the column
                        columns_to_keep_names.append(col_name)
                else: # `how == 'all'`
                    # If `all` values in `column_values` are NA, the column has all `None` and should be dropped.
                    all_na = all(is_na(val) for val in column_values)
                    if not all_na: # If not all NA, keep the column
                        columns_to_keep_names.append(col_name)
            
            # Create and return a new DataMolder instance containing only the kept columns
            # Why: Uses the dedicated `_create_molder_from_columns` helper for immutable column-wise filtering.
            self._save_version()

            return self._create_molder_from_columns(columns_to_keep_names)
    
    # --- Get Data ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def data_list(self, include_header: bool = False) -> Union[List[Tuple[Any, ...]], Tuple[Tuple[str, ...], List[Tuple[Any, ...]]], List[Any]]:
        """
        Converts the DataMolder instance into a list of tuples, where each tuple represents a row.
        Optionally includes the header (column names) as a tuple in the output or retrieves a specific column.
    
        Args:
            include_header (bool): Whether to include the header (column names) in the output.
                Defaults to False.
            column (Optional[str]): The name of the column to retrieve instead of rows.
                Defaults to None.
    
        Returns:
            Union[List[Tuple[Any, ...]], Tuple[Tuple[str, ...], List[Tuple[Any, ...]]], List[Any]]:
                - A list of tuples representing the rows if `column` is None.
                - A tuple containing the header (as a tuple) and the list of tuples if `include_header` is True.
                - A list of values from the specified column if `column` is provided.
    
        Raises:
            ColumnNotFoundError: If the specified column name does not exist.
    
        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.add_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25),
            ...     (3, "Charlie", 28)
            ... ])
            >>> DataMolder.data_list()
            [(1, "Alice", 30), (2, "Bob", 25), (3, "Charlie", 28)]
            >>> DataMolder.data_list(include_header=True)
            (('id', 'name', 'age'), [(1, "Alice", 30), (2, "Bob", 25), (3, "Charlie", 28)])
            >>> DataMolder.data_list(column="name")
            ['Alice', 'Bob', 'Charlie']
        """
        data = [tuple(self._data[col][i] for col in self.columns) for i in range(len(self))]
        if include_header:
            data = [tuple(self.columns)] + data
        return data   

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def head(self, n: int) -> List[Dict[str, Any]]:
        """
        Retrieves the first n rows from the DataMolder instance.

        Args:
            n (int): The number of rows to retrieve from the start.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the first n rows.
        """
        return self.get_items(slice(0, n)) 

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top    
    def tail(self, n: int) -> List[Dict[str, Any]]:
        """
        Retrieves the last n rows from the DataMolder instance.

        Args:
            n (int): The number of rows to retrieve from the end.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the last n rows.
        """
        return self.get_items(slice(-n, None))
 
    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def get_items(self, key: Union[int, List[int], slice], include_header: bool = False) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Retrieves one or multiple rows from the DataMolder instance by index, a list of indexes, or a slice.
    
        Args:
            indexes (Union[int, List[int], slice]): The index of the row to retrieve, a list of indexes,
            or a slice to retrieve multiple rows.
    
        Returns:
            Union[Dict[str, Any], List[Dict[str, Any]]]: A dictionary representing a single row, or a list of dictionaries
            representing multiple rows.
    
        Raises:
            IndexError: If any row index is out of range.
            TypeError: If the indexes are not an integer, list of integers, or slice.
    
        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.append_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25),
            ...     (3, "Charlie", 28)
            ... ])
            >>> DataMolder.get_items(1)
            {'id': 2, 'name': 'Bob', 'age': 25}
            >>> DataMolder.get_items([0, 2])
            [{'id': 1, 'name': 'Alice', 'age': 30}, {'id': 3, 'name': 'Charlie', 'age': 28}]
            >>> DataMolder.get_items(slice(1, 3))
            [{'id': 2, 'name': 'Bob', 'age': 25}, {'id': 3, 'name': 'Charlie', 'age': 28}]
        """
        if isinstance(key, int):
            # Single row retrieval using an integer index
            if key == -1:
                # Special case for -1 to return the last row
                key = len(self) - 1
            if not (0 <= key < len(self)):
                raise IndexError(f"Row index {key} is out of range.")            
            row_indexes = [key]        
        elif isinstance(key, slice):
            if key.start > key.stop:
                raise IndexError(f"Inconsistent row index range.")             
            elif not (0 <= key.start < len(self)):
                raise IndexError(f"Row index {key.start} is out of range.")
            elif not (0 <= key.stop < len(self.columns)):
                raise IndexError(f"Column index {key.stop} is out of range.")              
            row_indexes = range(len(self))[key]                          
        elif isinstance(key, (list, tuple)):
            # Multiple rows retrieval using a list of indexes
            if not all(isinstance(idx, int) for idx in key):
                raise TypeError("All elements in the list must be integers.")
            if not all(0 <= idx < len(self) for idx in key):
                raise IndexError("One or more row indexes are out of range.")
            row_indexes = key if isinstance(key, (list, tuple)) else [key]
        else:
            raise TypeError("Index must be an integer, slice, or list/tuple of integers.")    

        return [{col:self._data[col][i] for col in self.columns} for i in row_indexes]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def get_rows(self, indexes: Union[int, List[int], slice]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Retrieves one or multiple rows from the DataMolder instance by index, a list of indexes, or a slice.
    
        Args:
            indexes (Union[int, List[int], slice]): The index of the row to retrieve, a list of indexes,
            or a slice to retrieve multiple rows.
    
        Returns:
            Union[Dict[str, Any], List[Dict[str, Any]]]: A dictionary representing a single row, or a list of dictionaries
            representing multiple rows.
    
        Raises:
            IndexError: If any row index is out of range.
            TypeError: If the indexes are not an integer, list of integers, or slice.
    
        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.append_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25),
            ...     (3, "Charlie", 28)
            ... ])
            >>> DataMolder.get_rows(1)
            {'id': 2, 'name': 'Bob', 'age': 25}
            >>> DataMolder.get_rows([0, 2])
            [{'id': 1, 'name': 'Alice', 'age': 30}, {'id': 3, 'name': 'Charlie', 'age': 28}]
            >>> DataMolder.get_rows(slice(1, 3))
            [{'id': 2, 'name': 'Bob', 'age': 25}, {'id': 3, 'name': 'Charlie', 'age': 28}]
        """
        if isinstance(indexes, int):
            # Single row retrieval
            if not (0 <= indexes < len(self)):
                raise IndexError(f"Row index {indexes} is out of range.")
            row_indexes = [indexes] if indexes != -1 else [len(self) - 1]
        elif isinstance(indexes, (list,tuple)):
            # Multiple rows retrieval using list of indexes
            if not all(isinstance(idx, int) and 0 <= idx < len(self) for idx in indexes):
                raise IndexError("One or more row indexes are out of range.")
            row_indexes = indexes if isinstance(indexes, (list, tuple)) else [indexes]
        elif isinstance(indexes, slice):
            if indexes.start > indexes.stop:
                raise IndexError(f"Inconsistent row index range.")        
            elif not (0 <= indexes.start < len(self)):
                raise IndexError(f"Row index {indexes.start} is out of range.")
            elif not (0 <= indexes.stop < len(self.columns)):
                raise IndexError(f"Column index {indexes.stop} is out of range.")                               
            # Multiple rows retrieval using slice
            row_indexes = range(len(self))[indexes]
        else:
            raise TypeError("Index must be an integer, list/tuple of integers, or slice.")
        return [tuple(self._data[col][row_indexes] for col in self.columns) for row_indexes in row_indexes]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def get_columns(
        self,
        identifiers: Union[str, int, List[Union[str, int]], slice],
        row_slice: Optional[slice] = None
    ) -> Union[List[Any], Dict[str, List[Any]]]:
        """
        Description:
            Retrieves data for one or more columns, with an option to filter rows using a slice.
            This function is optimized for direct data access and minimal processing.

        Cost:
            - O(C_req * N_slice) where C_req is the number of requested columns and
              N_slice is the number of rows in the slice. For full columns, it's O(C_req * N).
            - The operation is highly efficient as it relies on direct dictionary lookups
              and fast list slicing.

        Args:
            identifiers (Union[str, int, List[Union[str, int]], slice]): The column(s) to retrieve.
                Can be a single name (str) or index (int), a list of names/indices, or a slice
                to select a range of columns.
            row_slice (Optional[slice]): An optional slice to apply to the rows of the
                selected columns, allowing for row filtering. Defaults to None (all rows).

        Returns:
            Union[List[Any], Dict[str, List[Any]]]: A list of values if a single column
            is requested, or a dictionary mapping column names to lists of values for
            multiple columns.

        Raises:
            ColumnNotFoundError: If any column name does not exist.
            IndexError: If any column index is out of range.
            TypeError: If an identifier has an invalid type.

        Example of use:
            # Get a single column by name
            names = dm.get_columns("name")
            # Get a single column by index, for the first 5 rows
            ages = dm.get_columns(2, row_slice=slice(0, 5))
            # Get multiple columns by list
            data = dm.get_columns(["id", "age"])
            # Get a slice of columns
            first_two_cols = dm.get_columns(slice(0, 2))
        """
        # --- Why: This block normalizes all possible inputs for `identifiers` into a
        # definitive list of names (`target_names`), making subsequent logic simpler.
        if isinstance(identifiers, (str, int)):
            # For a single identifier, we expect a single list back.
            name = self._resolve_column_name(identifiers)
            column_data = self._data[name]
            return column_data[row_slice] if row_slice else column_data.copy()

        if isinstance(identifiers, slice):
            # The slice applies to the list of columns.
            target_names = self.header.columns[identifiers]
        elif isinstance(identifiers, (list, tuple)):
            # Resolve each identifier in the list to its name.
            target_names = [self._resolve_column_name(i) for i in identifiers]
        else:
            raise TypeError("Identifiers must be a string, integer, list, tuple, or slice.")

        # --- Why: The main logic is a single loop over the requested columns. This is optimal
        # as we must process each column the user asked for.
        result = {}
        for name in target_names:
            column_data = self._data[name]
            # Why: Python's list slicing is highly optimized (implemented in C). Applying it
            # directly is much faster than iterating manually. `.copy()` is used for the
            # full column to prevent mutation of the internal data structure.
            result[name] = column_data[row_slice] if row_slice else column_data.copy()

        return result

    def _resolve_column_name(self, identifier: Union[str, int]) -> str:
        """
        Description:
            A private helper to convert a column identifier (int or str) into a
            validated column name string.

        Cost:
            - O(1) on average.

        Args:
            identifier (Union[str, int]): The column index or name.

        Returns:
            str: The validated column name.
            
        Raises:
            ColumnNotFoundError: If the column name does not exist.
            IndexError: If the column index is out of range.
            TypeError: If the identifier has an invalid type.
        """
        if isinstance(identifier, str):
            # Why: Using the pre-optimized `__contains__` on the Header (which uses a set)
            # makes this an efficient O(1) lookup.
            if identifier not in self.header:
                raise ColumnNotFoundError(f"Column '{identifier}' not found.")
            return identifier

        if isinstance(identifier, int):
            num_cols = len(self.header)
            if not (0 <= identifier < num_cols):
                raise IndexError(f"Column index {identifier} is out of range for {num_cols} columns.")
            return self.header.columns[identifier]
        
        raise TypeError(f"Column identifier must be a string or an integer, not {type(identifier).__name__}.")

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def get_cells(self, *args) -> Union[Any, List[Any]]:
        """
        Retrieves cell values from the DataMolder instance.

        This function supports flexible input formats for specifying cells:
        1. Single cell by `(row_index, column_identifier)`: Returns a single cell value.
        2. Multiple cells by `[(row1, col1), (row2, col2), ...]`: Returns a list of cell values.
        3. Single cell by two separate arguments: `get_cells(row_index, column_identifier)`.

        Cost:
            - O(1) for retrieving a single cell due to direct dictionary and list access.
            - O(K) for retrieving K cells, as it iterates K times and each cell retrieval is O(1).

        Args:
            *args: Variable arguments representing cell references.
                - If two arguments are provided: `(row_index: int, column_identifier: Union[str, int])`
                - If one argument is provided:
                    - `(cell_reference: Tuple[int, Union[str, int]])` for a single cell.
                    - `(cell_references: List[Tuple[int, Union[str, int]]])` for multiple cells.

        Returns:
            Union[Any, List[Any]]: The value of a single cell or a list of cell values.

        Raises:
            ValueError: If the cell reference format is invalid or arguments are malformed.
            IndexError: If any row or column index is out of range.
            ColumnNotFoundError: If a column name does not exist.
            TypeError: If row index or column identifier has an invalid type.

        Example of use:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.append_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25),
            ...     (3, "Charlie", 28)
            ... ])
            >>> DataMolder.get_cells(0, 0)
            1
            >>> DataMolder.get_cells((1, 'id'))
            2
            >>> DataMolder.get_cells([(0, 0), (1, 'name'), (2, 'age')])
            [1, 'Bob', 28]
        """
        # Why: Handle two separate arguments by converting them into a single tuple,
        # which simplifies subsequent processing. This avoids duplicating logic.
        if len(args) == 2:
            row_index, column_identifier = args
            return self._get_single_cell(row_index, column_identifier)

        # Why: Ensure there's exactly one argument for other valid formats.
        if len(args) != 1:
            raise ValueError("Invalid number of arguments. Expected one (tuple/list) or two (row, col).")

        cell_reference = args[0]

        # Why: Distinguish between a single cell tuple reference and a list of references.
        # This clear separation makes the logic more readable and maintainable.
        if isinstance(cell_reference, tuple):
            row_index, column_identifier = cell_reference
            return self._get_single_cell(row_index, column_identifier)
        elif isinstance(cell_reference, list):
            # Why: Use a list comprehension for efficient and concise processing of multiple cell references.
            # This is generally more Pythonic than a manual loop and append.
            return [self._get_single_cell(row, col) for row, col in cell_reference]
        else:
            # Why: Catching invalid types early helps in providing clear error messages to the user.
            raise TypeError("Cell reference must be a tuple (row, col) or a list of such tuples.")

    def _get_single_cell(self, row_index: int, column_identifier: Union[str, int]) -> Any:
        """
        Retrieves the value of a single cell based on row index and column identifier.

        This is a private helper method used by `get_cells` to centralize the logic
        for accessing individual cells and performing necessary validations.

        Cost:
            - O(1) as it involves direct dictionary and list lookups after initial validation.

        Args:
            row_index (int): The integer index of the row.
            column_identifier (Union[str, int]): The name (str) or index (int) of the column.

        Returns:
            Any: The value contained in the specified cell.

        Raises:
            IndexError: If the row index is out of range.
            ColumnNotFoundError: If the column identifier (name) does not exist.
            TypeError: If `row_index` is not an integer or `column_identifier` is not a string or integer.
            ValueError: If `column_identifier` is a string but empty.
        """
        # Why: Validate row index early to prevent out-of-bounds access.
        if not isinstance(row_index, int):
            raise TypeError(f"Row index must be an integer, got {type(row_index).__name__}.")
        if not (0 <= row_index < len(self)):
            raise IndexError(f"Row index {row_index} is out of range for {len(self)} rows.")

        # Why: Use the existing `_resolve_column_name` helper to consistently handle
        # both string and integer column identifiers, centralizing column validation.
        column_name = self._resolve_column_name(column_identifier)

        # Why: Direct access using dictionary keys and list indexing is the most efficient
        # way to retrieve the cell value, assuming data is stored column-wise.
        return self._data[column_name][row_index]

    def _get_column_by_index(self, col_idx: int) -> str:
        """
        Helper method to get column name from index.

        Args:
            col_idx (int): The integer index of the column.

        Returns:
            str: The name of the column.

        Raises:
            IndexError: If the column index is out of range.
        """     
        if not 0 <= col_idx < self.count_columns():
            raise IndexError(f"Column '{col_idx}' is out of range.")
                
        return self._column_enumerate[col_idx]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def to_dataframe(self) -> "pd.DataFrame":
        """
        Converts the DataMolder instance into a Pandas DataFrame.

        This method reconstructs the data into a Pandas DataFrame, preserving
        column names and data types.

        Returns:
            pd.DataFrame: A Pandas DataFrame representing the data in the DataMolder.

        Raises:
            ImportError: If pandas is not installed.

        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.add_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25)
            ... ])
            >>> df = DataMolder.to_dataframe()
            >>> print(df)
            id   name  age
            0   1  Alice   30
            1   2    Bob   25
        """
        # Because pandas is an optional dependency, it should be imported locally.
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("Pandas is not installed. Please install it to use this feature: pip install pandas")

        # Create a dictionary where keys are column names and values are lists of column data.
        # This approach is efficient as it directly uses the column-oriented storage.
        data_for_dataframe: Dict[str, List[Any]] = {col_name: self._data[col_name] for col_name in self.columns}

        # Construct the DataFrame from the dictionary.
        dataframe = pd.DataFrame(data_for_dataframe)

        return dataframe

    # --- Move Data ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top                
    def sort(self, by: Union[str, int, List[Union[str, int]], slice], ascending: Union[bool, List[bool]] = True) -> None:
        """
        Description:
            Sorts the rows in the DataMolder instance based on one or multiple columns.
            Bookmarks are updated to follow their respective rows to their new positions.
        
        Args:
            by (Union[str, int, List[Union[str, int]], slice]): Column(s) to sort by.
            ascending (Union[bool, List[bool]]): Sort order for the specified columns.
        
        Raises:
            ColumnNotFoundError: If a specified column does not exist.
            ValueError: If the length of `ascending` doesn't match the number of `by` columns.

        Cost: 
            O(N log N * M), where N is the number of rows and M is the number of sort columns.
        """
        if not self:
            return # Nothing to sort.

        # (Code for column name and sort order normalization remains the same)
        # ...
        
        # Why: This check for permissions prevents illegal modifications.
        for col_name in self.columns:
            if self.is_column_locked(col_name):
                raise PermissionError(f"Cannot sort: Column '{col_name}' is locked.")

        # (Assuming _normalize_sort_by_columns and _normalize_sort_order exist and work)
        column_names = self._normalize_sort_by_columns(by)
        ascending_orders = self._normalize_sort_order(ascending, len(column_names))

        # Why: `sorted_indexes` gives us a list where `sorted_indexes[new_index] = old_index`.
        # This is exactly what we need to reorder the data.
        sort_key_func = self._create_sort_key_function(column_names, ascending_orders)
        sorted_indexes = sorted(range(len(self)), key=sort_key_func)

        # --- Bookmark Update Logic ---
        # Why: To make bookmarks follow the data, we need a map from the old row index to
        # the new row index. We create an inverted map from `sorted_indexes` for this.
        # `old_to_new_map[old_index] = new_index`.
        old_to_new_map = {old_idx: new_idx for new_idx, old_idx in enumerate(sorted_indexes)}
        
        updated_bookmarks = {}
        for name, bm_index in self._bookmarks.items():
            updated_bookmarks[name] = old_to_new_map[bm_index]
        self._bookmarks = updated_bookmarks

        # --- Data and State Update ---
        # Why: Reorder all column data and metadata lists based on the sorted indexes.
        for col_name in self.columns:
            self._data[col_name] = [self._data[col_name][idx] for idx in sorted_indexes]
        
        self._modified = [self._modified[idx] for idx in sorted_indexes]
        
        if self._row_position != -1:
            self._row_position = old_to_new_map[self._row_position]

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def move_rows(self, row_indexes: Union[int, List[int]], position: Union[int, str]) -> None:
        """
        Description:
            Moves specified rows to a new position. Bookmarks and the cursor are
            updated to follow the rows to their new locations.

        Args:
            row_indexes (Union[int, List[int]]): The index or list of indexes of the rows to move.
            position (Union[int, str]): The target position: an integer index, "beginning", or "end".

        Raises:
            IndexError: If any source or destination index is out of range.
            ValueError: If the `position` string is invalid.
            TypeError: If inputs have an invalid type.

        Cost: 
            O(N*C), where N is the total number of rows and C is the number of columns,
            due to the reconstruction of column lists.
        """
        # 1. Normalize and Validate Inputs (row_indexes and position)
        if isinstance(row_indexes, int):
            row_indexes = [row_indexes]
        elif not isinstance(row_indexes, (list, tuple)) or not all(isinstance(idx, int) for idx in row_indexes):
            raise TypeError("Row indexes must be an integer or a list/tuple of integers.")

        if not all(0 <= idx < len(self) for idx in row_indexes):
            raise IndexError("One or more row indexes are out of range.")

        num_rows = len(self)
        target_pos: int
        if isinstance(position, str):
            if position == "beginning":
                target_pos = 0
            elif position == "end":
                target_pos = num_rows # The position *after* the remaining rows
            else:
                raise ValueError("Position must be 'beginning', 'end', or a valid integer index.")
        elif isinstance(position, int):
            if not (0 <= position <= num_rows):
                raise IndexError(f"Target position {position} is out of range [0, {num_rows}].")
            target_pos = position
        else:
            raise TypeError("Position must be an integer, 'beginning', or 'end'.")
        
        # 2. Construct the New Order of Original Indices
        # Why: This is the core of the refactor. We determine the final arrangement of the
        # original row indexes before touching any data. This gives us a definitive map for reordering.
        
        # Use a set for efficient lookup (O(1)) and sort to maintain user-specified order for moved items.
        moved_indices_set = set(row_indexes)
        moved_indices_ordered = sorted([idx for idx in row_indexes if idx in moved_indices_set], key=row_indexes.index)

        remaining_indices = [i for i in range(num_rows) if i not in moved_indices_set]
        
        # Why: The target position must be adjusted based on how many of the rows being
        # moved were originally before it. This gives us the correct insertion point
        # within the list of *remaining* rows.
        num_moved_before_target = sum(1 for idx in moved_indices_ordered if idx < target_pos)
        adjusted_position = target_pos - num_moved_before_target

        # This list is the equivalent of `sorted_indexes` or `shuffled_indices`.
        new_order_of_old_indices = (
            remaining_indices[:adjusted_position] +
            moved_indices_ordered +
            remaining_indices[adjusted_position:]
        )

        # 3. Create the Index Map and Update Bookmarks/Cursor
        # Why: Now that we have the new order, we can create the old-to-new map and update
        # state, just like in the other functions.
        old_to_new_map = {old_idx: new_idx for new_idx, old_idx in enumerate(new_order_of_old_indices)}

        updated_bookmarks = {}
        for name, bm_index in self._bookmarks.items():
            updated_bookmarks[name] = old_to_new_map[bm_index]
        self._bookmarks = updated_bookmarks

        if self._row_position != -1:
            self._row_position = old_to_new_map[self._row_position]

        # 4. Reorder Data Based on the New Index Order
        # Why: This unified approach is cleaner and less error-prone than the previous
        # method of extracting and re-inserting data for each column separately.
        for col_name in self.columns:
            self._data[col_name] = [self._data[col_name][i] for i in new_order_of_old_indices]
        
        self._modified = [self._modified[i] for i in new_order_of_old_indices]

        if self._row_position < 1: self._row_position = self._num_rows

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def move_columns(self, column_indexes: Union[int, str, List[Union[int, str]]], position: Union[int, str]) -> None:
        """
        Moves specified columns to a specific position in the DataMolder instance.

        The `column_indexes` can be integer indices or column names. The `position`
        can be an integer index (0-based) or the keywords "beginning" or "end".
        This method reorders the logical column order managed by the Header.

        Args:
            column_indexes (Union[int, str, List[Union[int, str]]]): The index (integer)
                                                                    or name (string) of a single column,
                                                                    or a list of such indexes/names,
                                                                    representing the columns to move.
            position (Union[int, str]): The target position for the columns. Can be an integer index,
                                        "beginning" (equivalent to 0), or "end" (equivalent to
                                        `len(self.columns)` after other columns have been removed).

        Raises:
            ColumnNotFoundError: If any column name provided in `column_indexes` does not exist.
            IndexError: If any column index in `column_indexes` is out of range, or if the
                        target `position` is invalid.
            ValueError: If the `position` string is not "beginning" or "end".
            TypeError: If the `column_indexes` are not an integer, string, or a list/tuple
                    containing integers or strings; or if `position` is an invalid type.

        Cost:
            O(C_total), where C_total is the total number of columns. This is because
            the operation primarily involves manipulating a list of column names.

        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int),
            ...     ("name", str),
            ...     ("age", int),
            ...     ("department", str)
            ... ])
            >>> DataMolder.add_row((1, "Alice", 30, "Sales"))
            >>> DataMolder.columns
            ['id', 'name', 'age', 'department']

            >>> # Move columns by name to the beginning
            >>> DataMolder.move_columns(["department", "age"], position="beginning")
            >>> DataMolder.columns
            ['department', 'age', 'id', 'name']

            >>> # Move columns by index to the end
            >>> DataMolder.move_columns([0, 2], position="end") # Assuming current: department (0), age (1), id (2), name (3)
            >>> DataMolder.columns # 'department' (0) and 'id' (2) moved to end
            ['age', 'name', 'department', 'id']
        """
        # 1. Normalize column_indexes to a list of unique column names
        column_names_to_move_set = set()
        column_names_to_move_ordered: List[str] = []

        if isinstance(column_indexes, (int, str)):
            # Convert single index/name to a list for uniform processing
            column_identifiers = [column_indexes]
        elif isinstance(column_indexes, (list, tuple)):
            column_identifiers = column_indexes
        else:
            raise TypeError("Column indexes must be an integer, string, or a list/tuple of integers/strings.")

        current_column_names = self.header.column_names

        for col_identifier in column_identifiers:
            col_name: str
            if isinstance(col_identifier, int):
                if not (0 <= col_identifier < len(current_column_names)):
                    raise IndexError(f"Column index {col_identifier} is out of range.")
                col_name = current_column_names[col_identifier]
            elif isinstance(col_identifier, str):
                if col_identifier not in current_column_names:
                    raise ColumnNotFoundError(f"Column '{col_identifier}' not found.")
                col_name = col_identifier
            else:
                raise TypeError("Elements in column_indexes must be strings (column names) or integers (column indexes).")

            if col_name not in column_names_to_move_set:
                column_names_to_move_set.add(col_name)
                column_names_to_move_ordered.append(col_name) # Preserve original input order for moved columns

        # Handle trivial case: no columns to move after normalization
        if not column_names_to_move_ordered:
            return

        # 2. Normalize position
        num_current_columns = len(current_column_names)
        target_pos: int

        if isinstance(position, str):
            if position == "beginning":
                target_pos = 0
            elif position == "end":
                target_pos = num_current_columns
            else:
                raise ValueError("Position must be 'beginning', 'end', or a valid integer index.")
        elif isinstance(position, int):
            if not (0 <= position <= num_current_columns):
                raise IndexError(f"Target position {position} is out of range [0, {num_current_columns}].")
            target_pos = position
        else:
            raise TypeError("Position must be an integer, 'beginning', or 'end'.")

        # 3. Determine remaining columns and calculate adjusted target position
        remaining_column_names = [
            col for col in current_column_names if col not in column_names_to_move_set
        ]

        # Calculate how many of the *moved* columns were originally *before* the target_pos
        # This is needed to adjust the target_pos after these columns are logically "removed"
        # from their original spots.
        num_moved_before_target = sum(
            1 for col_name in column_names_to_move_ordered 
            if current_column_names.index(col_name) < target_pos
        )
        adjusted_position = target_pos - num_moved_before_target

        # 4. Reconstruct self.header.column_names
        new_column_names = (
            remaining_column_names[:adjusted_position] +
            column_names_to_move_ordered +
            remaining_column_names[adjusted_position:]
        )
        self.header.column_names = new_column_names

        self._save_version()

    def _swap_rows(self, row_indexes1: List[int], row_indexes2: List[int]) -> None:
        """
        Description:
            Swaps rows within the DataMolder instance. Bookmarks are updated
            to reflect the swapped row positions.

        Args:
            row_indexes1 (List[int]): A list of integer row indexes to swap.
            row_indexes2 (List[int]): A list of integer row indexes to swap with.

        Raises:
            ValueError: If the lengths of the index lists do not match.
            IndexError: If any row index is out of range.

        Cost: 
            O(num_rows_to_swap * num_columns).
        """
        if len(row_indexes1) != len(row_indexes2):
            raise ValueError("The lengths of row_indexes1 and row_indexes2 must match for row swapping.")

        if not all(0 <= idx < len(self) for idx in row_indexes1 + row_indexes2):
            raise IndexError("One or more row indexes are out of range.")

        # --- Bookmark Update Logic ---
        # Why: Create a mapping for all swaps in both directions. This allows us to find
        # the new position of a bookmarked row in a single O(1) lookup.
        swap_map = {**dict(zip(row_indexes1, row_indexes2)), **dict(zip(row_indexes2, row_indexes1))}
        
        updated_bookmarks = {}
        for name, bm_index in self._bookmarks.items():
            # Why: If the bookmark's index is part of the swap, update it to its new
            # position from the map. Otherwise, it remains unchanged.
            updated_bookmarks[name] = swap_map.get(bm_index, bm_index)
        self._bookmarks = updated_bookmarks

        # --- Data and State Update ---
        for idx1, idx2 in zip(row_indexes1, row_indexes2):
            for col_name in self.columns:
                self._data[col_name][idx1], self._data[col_name][idx2] = self._data[col_name][idx2], self._data[col_name][idx1]
            
            self._modified[idx1], self._modified[idx2] = self._modified[idx2], self._modified[idx1]

        if self._row_position != -1:
            self._row_position = swap_map.get(self._row_position, self._row_position)

        if self._row_position < 1: self._row_position = self._num_rows

        self._save_version()

    def _swap_columns(self, col_names1: List[str], col_names2: List[str]) -> None:
        """
        Swaps columns within the DataMolder instance.

        This private helper method performs the actual swapping of columns based on
        the provided lists of column names. It validates the column names and
        ensures the lengths of the column name lists match before swapping the
        internal data structures and updating the column order.

        Args:
            col_names1 (List[str]): A list of column names to swap.
            col_names2 (List[str]): A list of column names to swap with.

        Raises:
            ValueError:
                If the lengths of `col_names1` and `col_names2` do not match,
                as an equal number of columns must be specified for a pairwise swap.
            ColumnNotFoundError:
                If any of the provided column names do not exist in the DataMolder.
                This ensures that only valid columns are targeted for swapping.

        Cost: O(num_columns_to_swap), where num_columns_to_swap is the length of `col_names1`.
              This is because for each pair of columns being swapped,
              only the pointers to their data lists and their positions in the
              `self.columns` list need to be exchanged. The actual data is not moved.
        """
        # Ensure that an equal number of column names are provided for pairwise swapping.
        if len(col_names1) != len(col_names2):
            raise ValueError("The lengths of col_names1 and col_names2 must match for column swapping.")

        # Check if all specified column names exist in the DataMolder's header.
        # This prevents KeyError when accessing non-existent columns.
        if not all(col_name in self.header for col_name in col_names1 + col_names2):
            raise ColumnNotFoundError("One or more column names do not exist.")

        # Iterate through pairs of column names and swap their corresponding data lists
        # and update their positions in the `self.columns` list.
        for col1, col2 in zip(col_names1, col_names2):
            # Swap the actual data lists for the two columns in the internal `_data` dictionary.
            # This efficiently re-points the column names to the swapped data.
            self._data[col1], self._data[col2] = self._data[col2], self._data[col1]

            # Update the order of column names in the `self.columns` list.
            # This maintains the correct sequence of columns after the swap.
            idx1, idx2 = self.columns.index(col1), self.columns.index(col2)
            self.columns[idx1], self.columns[idx2] = self.columns[idx2], self.columns[idx1]

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def swap(self, indexes1: Union[int, List[int], str, List[str]], indexes2: Union[int, List[int], str, List[str]]) -> None:
        """
        Swaps rows or columns in the DataMolder instance.

        This method supports swapping rows by integer indexes or columns by string names.
        It intelligently determines whether to perform a row swap or a column swap
        based on the type of the provided indexes. Single indexes are automatically
        converted to lists for consistent processing.

        Args:
            indexes1 (Union[int, List[int], str, List[str]]):
                The index or list of indexes of rows to swap (integers), or
                the name or list of names of columns to swap (strings).
            indexes2 (Union[int, List[int], str, List[str]]):
                The index or list of indexes of rows to swap with (integers), or
                the name or list of names of columns to swap with (strings).

        Raises:
            IndexError:
                If any row index is out of the valid range when swapping rows.
            ColumnNotFoundError:
                If any column name does not exist when swapping columns.
            ValueError:
                If the lengths of the two lists of indexes/names do not match.
            TypeError:
                If the indexes are not consistent (e.g., mixing integers and strings in a list),
                or if the types of `indexes1` and `indexes2` are not compatible
                (e.g., trying to swap an integer index with a string name).

        Example of use:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.add_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25),
            ...     (3, "Charlie", 28)
            ... ])
            >>> print("Original rows:", DataMolder.get_rows(slice(0, 3)))
            Original rows: [{'id': 1, 'name': 'Alice', 'age': 30}, {'id': 2, 'name': 'Bob', 'age': 25}, {'id': 3, 'name': 'Charlie', 'age': 28}]

            >>> DataMolder.swap(0, 2)  # Swap rows by indexes
            >>> print("Rows after swapping 0 and 2:", DataMolder.get_rows(slice(0, 3)))
            Rows after swapping 0 and 2: [{'id': 3, 'name': 'Charlie', 'age': 28}, {'id': 2, 'name': 'Bob', 'age': 25}, {'id': 1, 'name': 'Alice', 'age': 30}]

            >>> print("Original columns:", DataMolder.get_columns())
            Original columns: ['id', 'name', 'age']

            >>> DataMolder.swap(["name", "age"], ["age", "name"])  # Swap columns by lists of names
            >>> print("Columns after swapping 'name' and 'age':", DataMolder.get_columns())
            Columns after swapping 'name' and 'age': ['id', 'age', 'name']

            >>> # Example of swapping a single column name
            >>> DataMolder_cols = DataMolder([("A", int, None, False, False), ("B", int, None, False, False)])
            >>> DataMolder_cols.add_rows([(1, 2)])
            >>> print("Original columns for single swap:", DataMolder_cols.get_columns())
            Original columns for single swap: ['A', 'B']
            >>> DataMolder_cols.swap("A", "B")
            >>> print("Columns after single swap A and B:", DataMolder_cols.get_columns())
            Columns after single swap A and B: ['B', 'A']

        Cost:
            The cost depends on whether rows or columns are being swapped:
            - If swapping rows: O(num_rows_to_swap * num_columns), where 'num_rows_to_swap'
              is the number of row pairs being swapped (length of `indexes1` or `indexes2`),
              and 'num_columns' is the total number of columns in the DataMolder. This is
              because each cell in the affected rows across all columns must be accessed.
            - If swapping columns: O(num_columns_to_swap), where 'num_columns_to_swap'
              is the number of column pairs being swapped. This is generally much faster
              than row swapping as it involves pointer manipulation (swapping references
              to data lists) rather than moving individual data points.
        """
        # Normalize inputs to lists for consistent handling.
        normalized_indexes1 = self._normalize_indexes(indexes1)
        normalized_indexes2 = self._normalize_indexes(indexes2)

        # Determine if we are swapping rows or columns based on the type of the normalized indexes.
        # It's crucial that both sets of indexes are of the same type for a valid swap operation.
        is_row_swap = all(isinstance(idx, int) for idx in normalized_indexes1)
        is_column_swap = all(isinstance(idx, str) for idx in normalized_indexes1)

        # Check if the types of indexes1 and indexes2 are consistent.
        if (is_row_swap and not all(isinstance(idx, int) for idx in normalized_indexes2)) or \
           (is_column_swap and not all(isinstance(idx, str) for idx in normalized_indexes2)):
            raise TypeError("Both sets of indexes must be of the same type (all integers for rows or all strings for columns).")

        # Delegate to the appropriate helper method based on the determined swap type.
        if is_row_swap:
            self._swap_rows(normalized_indexes1, normalized_indexes2)
        elif is_column_swap:
            self._swap_columns(normalized_indexes1, normalized_indexes2)
        else:
            # This case should ideally be caught by _normalize_indexes, but
            # it acts as a safeguard against unexpected input types.
            raise TypeError("Indexes must be integers (row indexes) or strings (column names).")

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def shuffle(self) -> None:
        """
        Description:
            Randomly shuffles the rows of the DataMolder instance in-place.
            Bookmarks and the current cursor position are updated to follow the
            data to their new, shuffled locations.

        Cost: 
            O(N*C), where N is the number of rows and C is the number of columns.
            The primary cost comes from reordering the data in each column list.

        Example of use:
            >>> # (Assuming DataMolder is populated)
            >>> DataMolder.add_bookmark("my_bookmark") # Cursor is at the bookmarked row
            >>> original_row = DataMolder.current_row
            >>> DataMolder.shuffle()
            >>> DataMolder.goto_bookmark("my_bookmark")
            >>> shuffled_row = DataMolder.current_row
            >>> # original_row and shuffled_row will contain the same data,
            >>> # even though their index has changed.
        """
        num_rows = len(self)
        if num_rows <= 1:
            # Why: Shuffling is not necessary for 0 or 1 rows.
            return

        # Why: Check for permissions before making any changes.
        for column_name in self.columns:
            if self.is_column_locked(column_name):
                raise PermissionError(f"Cannot shuffle: Column '{column_name}' is locked.")

        # Why: The `shuffled_indices` list provides the new order. The element at
        # `shuffled_indices[new_index]` is the `old_index` of the row that now
        # resides at `new_index`.
        shuffled_indices = list(range(num_rows))
        random.shuffle(shuffled_indices)

        # --- Bookmark and Cursor Update Logic ---
        # Why: To make bookmarks and the cursor follow the data, we create a map from
        # the old row index to the new row index. This is the inverse of `shuffled_indices`.
        old_to_new_map = {old_idx: new_idx for new_idx, old_idx in enumerate(shuffled_indices)}

        updated_bookmarks = {}
        for name, bm_index in self._bookmarks.items():
            updated_bookmarks[name] = old_to_new_map[bm_index]
        self._bookmarks = updated_bookmarks

        if self._row_position != -1:
            self._row_position = old_to_new_map[self._row_position]

        # --- Data and State Update ---
        # Why: Reorder all column data and metadata lists based on the shuffled indices.
        # This is more readable and consistent than other reordering methods.
        for column_name in self.columns:
            self._data[column_name] = [self._data[column_name][i] for i in shuffled_indices]

        self._modified = [self._modified[i] for i in shuffled_indices]

        self._save_version()

    # --- Update Data ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def update_cell(self, row_index: int, column: str, value: Any) -> None:
        """
        Updates the value of a specific cell in the DataMolder instance.
    
        Args:
            row_index (int): The index of the row to update.
            column (str): The name of the column to update.
            value (Any): The new value to set for the specified cell.
    
        Raises:
            IndexError: If the row index is out of range.
            ColumnNotFoundError: If the column name does not exist.
            TypeValidationError: If the value does not match the expected type for the column.
            ConstraintValidationError: If the value fails the custom validator for the column.
    
        Examples:
            >>> DataMolder = DataMolder([
            ...     ("id", int, None, True, True),
            ...     ("name", str, None, True, False),
            ...     ("age", int, 0, False, False)
            ... ])
            >>> DataMolder.append_rows([
            ...     (1, "Alice", 30),
            ...     (2, "Bob", 25)
            ... ])
            >>> DataMolder.update_cell(1, "name", "Bob Smith")
            >>> DataMolder.get_row(1)
            {'id': 2, 'name': 'Bob Smith', 'age': 25}
    
            >>> DataMolder.update_cell(0, "age", 31)
            >>> DataMolder.get_row(0)
            {'id': 1, 'name': 'Alice', 'age': 31}
        """
        # Validate row index
        if not (0 <= row_index < len(self)):
            raise IndexError(f"Row index {row_index} is out of range.")
    
        # Validate column name
        if column not in self.header:
            raise ColumnNotFoundError(f"Column '{column}' not found.")
    
        # Validate value type and constraints
        if self.validate_on_change:
            self.header.validate(column, value)
    
        # Update the value
        self._data[column][row_index] = value
        self._modified[row_index] = True

        # If validation is deferred, mark the DataMolder as not fully validated
        if not self.validate_on_change:
            self._is_validated = False

        # Why: If the updated column is a dependency, trigger re-computation
        # for all dependent columns in the affected row.
        if column in self._source_column_dependents:
            for dependent_col in self._source_column_dependents[column]:
                self._recompute_cell(row_index, dependent_col)

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def update_rows(self, row_indexes: Union[int, List[int]], columns: Union[List[str], List[int], slice], values: List[Any]) -> None:
        """
        Updates specific cells in one or multiple rows of the DataMolder instance.
    
        Args:
            row_indexes (Union[int, List[int]]): The index of the row to update, or a list of row indexes.
            columns (Union[List[str], List[int], slice]): The names, indexes, or a slice of the columns to update.
            values (List[Any]): The new values to set for the specified columns.
    
        Raises:
            IndexError: If any row index is out of range.
            ColumnNotFoundError: If any column name or index does not exist.
            ValueError: If the number of columns does not match the number of values.
            TypeError: If the columns are neither a list of strings, a list of integers, nor a slice.
    
        Examples:
            >>> DataMolder.update_rows(1, ["name", "age"], ["Alice Smith", 31])
            >>> DataMolder.get_row(1)
            {'id': 2, 'name': 'Alice Smith', 'age': 31, 'department': 'Marketing', 'salary': 65000.0, 'active': True}
    
            >>> DataMolder.update_rows([0, 2], slice(3, 4), ["HR", "Marketing"])
            >>> DataMolder.get_row([0, 2])
            [{'id': 1, 'name': 'John Smith', 'age': 30, 'department': 'HR', 'salary': 75000.0, 'active': True},
             {'id': 3, 'name': 'Peter Brown', 'age': 35, 'department': 'Marketing', 'salary': 85000.0, 'active': True}]
        """
        if not isinstance(row_indexes, (int, list)):
            raise TypeError("Row indexes must be an integer or a list of integers.")
        if not isinstance(columns, (list, slice)) or (isinstance(columns, list) and not all(isinstance(col, (str, int)) for col in columns)):
            raise TypeError("Columns must be a list of strings, a list of integers, or a slice.")
        if not isinstance(values, list) or len(columns) != len(values) if isinstance(columns, list) else len(range(len(self.columns))[columns]) != len(values):
            raise ValueError("The number of columns must match the number of values.")
    
        # Ensure row_indexes is a list for uniform processing
        if isinstance(row_indexes, int):
            row_indexes = [row_indexes]
    
        # Validate row indexes
        if not all(0 <= idx < len(self) for idx in row_indexes):
            raise IndexError("One or more row indexes are out of range.")
    
        # Convert column indexes or slice to column names if necessary
        column_names = []
        if isinstance(columns, slice):
            if columns.start > columns.stop:
                raise IndexError(f"Inconsistent row index range.")    
            elif not (0 <= columns.start < len(self)):
                raise IndexError(f"Row index {columns.start} is out of range.")
            elif not (0 <= columns.stop < len(self.columns)):
                raise IndexError(f"Column index {columns.stop} is out of range.")   
            else:
                raise TypeError("Key must be an integer, slice, or list of integers.")                                
            column_names = self.columns[columns]
        else:
            for col in columns:
                if isinstance(col, int):
                    if not (0 <= col < len(self.columns)):
                        raise IndexError(f"Column index {col} is out of range.")
                    column_names.append(self.columns[col])
                elif isinstance(col, str):
                    if col not in self.header:
                        raise ColumnNotFoundError(f"Column '{col}' not found.")
                    column_names.append(col)
                else:
                    raise TypeError("Columns must be strings (column names), integers (column indexes), or a slice.")
    
        # Update values for each row and column using list compression for efficiency.
        for col, vals in zip(column_names, zip(*values)):
            for row_idx, value in zip(row_indexes, vals):
                self._data[col][row_idx] = value
                self._modified[row_idx] = True 

        # Why: Check all updated columns to see if they are dependencies and
        # trigger re-computation for all affected rows and dependent columns.
        for col_name in column_names:
            if col_name in self._source_column_dependents:
                for dependent_col in self._source_column_dependents[col_name]:
                    for row_idx in row_indexes:
                        self._recompute_cell(row_idx, dependent_col)

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def transform(self, transformations: Dict[str, Callable[[Any], Any]]) -> 'DataMolder':
        """
        Apply transformations to the data.

        This method applies specified transformation functions to the corresponding columns.
        It modifies the data in-place for efficiency by using list comprehensions.

        Args:
            transformations: A dictionary where keys are column names (str) and
                            values are callable functions (Callable[[Any], Any])
                            that take a single value from the column and return
                            the transformed value.

        Returns:
            DataMolder: The current DataMolder instance, allowing for method chaining.

        Raises:
            ValueError: If no data has been loaded into the DataMolder.
            KeyError: If a specified column for transformation does not exist.

        Computational Cost:
            O(N * M), where N is the number of rows (length of columns) and M is
            the number of columns being transformed. Each transformation function's
            cost is also a factor. The list comprehension ensures optimal performance
            for in-memory Python lists.

        Examples:
            >>> dm = DataMolder([("value", int)])
            >>> dm.add_rows([(1,), (2,), (3,), (4,), (5,)]) # Add some sample data
            >>> dm.transform({"value": lambda x: x * 2})
            >>> print(dm._data["value"])
            [2, 4, 6, 8, 10]
        """
        # Ensure that _data is not empty before attempting transformations.
        # This check is crucial for preventing errors when no data is loaded.
        if not self._data or not any(self._data.values()):
            raise ValueError("No data loaded. Call add_rows() first.")

        # Check for locked columns before proceeding
        for column_name in transformations:
            if self.is_column_locked(column_name):
                raise PermissionError(f"Column '{column_name}' is locked and cannot be transformed.")

        # Iterate over each specified transformation.
        for column_name, transform_function in transformations.items():
            # Validate that the column exists in the DataMolder's internal data structure.
            if column_name not in self._data:
                raise KeyError(f"Column '{column_name}' not found in DataMolder.")

            # Apply the transformation to the entire column using a list comprehension.
            # This is generally the most performant way to transform elements in a Python list.
            # It creates a new list with the transformed values and replaces the old list,
            # which is efficient for in-place updates of columns.
            self._data[column_name] = [transform_function(value) for value in self._data[column_name]]

        # Why: If a transformed column is a dependency, all dependent
        # computed columns must be fully recomputed.
        if column_name in self._source_column_dependents:
            for dependent_col in self._source_column_dependents[column_name]:
                self._recompute_column(dependent_col)

        self._save_version()
        return self

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def map(self, func: Callable[..., Tuple[Any, ...]]) -> 'DataMolder':
        """
        Description:
            Applies a function to each row and returns a new DataMolder with the results.

        Description:
            This method is optimized to perform all transformations first, collecting the
            results, and then uses the efficient `append_rows` to build the new DataMolder
            instance in a single, bulk operation.

        Args:
            func (Callable[..., Tuple[Any, ...]]): A function that transforms one row tuple into another.

        Returns:
            DataMolder: A new DataMolder instance with the transformed data.

        Raises:
            ValueError: If the mapping function returns inconsistent row lengths.

        Example of use:
            >>> new_dm = dm.map(lambda row: (row[0], row[1].upper()))
            
        Cost: 
            O(R * C_old + R * C_new), where R is rows, and C is columns for the old and new data.
            The cost is dominated by the initial iteration and the final bulk append.
        """
        if not self:
            return DataMolder(self.columns) # Return an empty molder with the same schema

        # Why: Use a list comprehension to apply the transformation to all rows at once.
        # This is generally faster than a for-loop with `append`.
        transformed_rows = [func(row) for row in self]

        if not transformed_rows:
            return DataMolder([]) # Should not happen if self is not empty, but safe.
            
        # --- Infer Schema from the first result ---
        first_transformed_row = transformed_rows[0]
        if not isinstance(first_transformed_row, tuple):
            raise TypeError("The map function must return a tuple for each row.")
        
        num_new_cols = len(first_transformed_row)
        new_column_definitions = [
            (f"col_{i}", type(value)) for i, value in enumerate(first_transformed_row)
        ]

        # --- Create and Populate New DataMolder ---
        # Why: Create the new instance and use the optimized `append_rows` method
        # for efficient bulk population. This avoids the per-row overhead of `add_row`.
        new_DataMolder = DataMolder(new_column_definitions)
        new_DataMolder.append_rows(transformed_rows)

        self._save_version()
        return new_DataMolder

    # --- Slicing and Views ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def print(self, num_display_rows: int = 50, tablefmt: str = "simple") -> None:
        """
        Prints a tabular representation of the DataMolder content using the tabulate library.

        Description:
            This method provides a formatted console output of the DataMolder's data.
            It displays the header and a specified number of rows. If the total number
            of rows exceeds twice 'num_display_rows', it will show the top 'num_display_rows'
            and the bottom 'num_display_rows' with an ellipsis row in between, similar to
            pandas DataFrame. This method performs a lazy import of the `tabulate` library.

        Args:
            num_display_rows (int): The number of rows to display from the beginning and end
                                    if the total number of rows is large. Defaults to 50.
            tablefmt (str): The table format to use for tabulate (e.g., 'plain', 'simple',
                            'grid', 'fancy_grid', 'pipe', 'orgtbl', 'jira', 'presto',
                            'psql', 'rst', 'mediawiki', 'moinmoin', 'textile', 'html', 'latex',
                            'latex_raw', 'tsv', 'json', 'github', 'outline', 'pretty').
                            Defaults to 'simple'.

        Returns:
            None: The method prints directly to the console.

        Raises:
            TypeError: If num_display_rows is not an integer or tablefmt is not a string.
            ValueError: If num_display_rows is negative.
            ImportError: If the 'tabulate' library is not installed.

        Example of use:
            >>> dm = DataMolder([("id", int), ("name", str)])
            >>> dm.add_rows([(i, f"Name_{i}") for i in range(150)])
            >>> dm.print()
            # This will print the first 50 rows, an ellipsis, and then the last 50 rows.

            >>> dm_small = DataMolder([("id", int)])
            >>> dm_small.add_rows([(i,) for i in range(20)])
            >>> dm_small.print()
            # This will print all 20 rows.

            >>> dm_small.print(tablefmt="grid")
            # This will print all 20 rows using the 'grid' format.

        Cost:
            O(N_displayed * C) where N_displayed is the number of rows actually printed
            (at most 2 * num_display_rows + 1 for ellipsis) and C is the number of columns.
            Additional cost for string formatting and console output by tabulate.
        """
        # Lazy import of tabulate to avoid unnecessary dependency loading
        try:
            from tabulate import tabulate
        except ImportError:
            raise ImportError(
                "The 'tabulate' library is required to use the print method. "
                "Please install it with: pip install tabulate"
            )

        # Validate inputs for `num_display_rows` and `tablefmt`
        if not isinstance(num_display_rows, int):
            raise TypeError(f"num_display_rows must be an integer, got {type(num_display_rows).__name__}")
        if num_display_rows < 0:
            raise ValueError("num_display_rows must be non-negative")
        if not isinstance(tablefmt, str):
            raise TypeError(f"tablefmt must be a string, got {type(tablefmt).__name__}")

        # Prepare headers for the table
        headers = list(self.header.columns)
        all_rows_data = []

        num_total_rows = len(self)

        # Determine which rows to display based on total rows and display limit
        if num_total_rows <= 2 * num_display_rows:
            # Display all rows if the total count is small or moderate
            # Why: Avoids unnecessary ellipsis for datasets that fit comfortably on screen.
            for row_idx in range(num_total_rows):
                row = [self._data[col][row_idx] for col in self.header.columns]
                all_rows_data.append(row)
        else:
            # Display head and tail with an ellipsis for very large datasets
            # Why: Provides a concise overview of dataset structure and content
            # without overwhelming the console with all rows.
            head_indices = range(num_display_rows)
            for row_idx in head_indices:
                row = [self._data[col][row_idx] for col in self.header.columns]
                all_rows_data.append(row)

            # Add ellipsis row to indicate truncated data
            # Why: Visually separates the head and tail, clearly indicating omitted rows.
            all_rows_data.append(["..." for _ in headers]) 

            tail_indices_start = num_total_rows - num_display_rows
            for row_idx in range(tail_indices_start, num_total_rows):
                row = [self._data[col][row_idx] for col in self.header.columns]
                all_rows_data.append(row)

        # Print the table using the tabulate library
        print(tabulate(all_rows_data, headers=headers, tablefmt=tablefmt))

    def _create_molder_from_indices(self, row_indices: List[int]) -> 'DataMolder':
        """
        Helper method to create a new DataMolder by copying specific rows.

        Description:
            This private method encapsulates the common logic for creating a new
            DataMolder instance and populating it with rows specified by their indices.
            It ensures data integrity by directly copying values from the specified rows,
            assuming the source data is already valid.

        Args:
            row_indices (List[int]): A list of integer row indices to copy into the new DataMolder.

        Returns:
            DataMolder: A new DataMolder instance containing the specified rows.

        Raises:
            None: This method relies on pre-validated indices.

        Example of use:
            # Example assuming 'self' is an instance of DataMolder
            # new_molder = self._create_molder_from_indices(list(range(5))) # For head(5)
            # new_molder = self._create_molder_from_indices(list(range(len(self)))) # For copy()

        Cost:
            O(N_selected * C) where N_selected is the number of rows specified in row_indices
            and C is the number of columns, due to copying individual elements.
        """
        # Build new molder with the same schema and validation settings
        new_defs = [
            (
                col,
                self.header.get_type(col),
                self.header.get_default(col),
                self.header.is_required(col),
                self.header.is_key(col)
            )
            for col in self.header.columns
        ]
        new_molder = DataMolder(new_defs, validate_on_change=self.validate_on_change)

        num_rows_to_copy = len(row_indices)

        # Populate the new molder's data based on the provided indices
        # Why: This allows flexible copying of contiguous or non-contiguous rows
        # while still being efficient by avoiding add_rows overhead.
        for col in self.header.columns:
            new_molder._data[col] = [self._data[col][idx] for idx in row_indices]

        # Update the number of rows in the new molder
        new_molder._num_rows = num_rows_to_copy
        # If the original molder has key fields, rebuild the key set for the new molder
        # Why: The key set must reflect only the keys present in the new, copied data.
        if new_molder._key_fields:
            new_molder._key_set = {
                tuple(new_molder._data[k][i] for k in new_molder._key_fields)
                for i in range(new_molder._num_rows)
            }
        # Mark all rows as modified in the new molder as they are newly populated.
        new_molder._modified = [True] * new_molder._num_rows

        return new_molder

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def head(self, n: int = 5) -> 'DataMolder':
        """
        Return a new DataMolder with the first `n` rows (immutable copy with validation).

        Description:
            This method creates an immutable copy of the current DataMolder instance
            containing only the first 'n' rows. It ensures data integrity through
            type and constraint validation, leveraging efficient internal data copying.

        Args:
            n (int): The number of rows to include from the beginning of the DataMolder.
                     Defaults to 5.

        Returns:
            DataMolder: A new DataMolder instance containing the first 'n' rows.

        Raises:
            TypeError: If `n` is not an integer.
            ValueError: If `n` is negative.

        Example of use:
            >>> dm = DataMolder([("id", int)])
            >>> dm.add_rows([(1,), (2,), (3,), (4,), (5,), (6,)])
            >>> head_dm = dm.head(3)
            >>> len(head_dm)
            3

        Cost:
            O(N * C) where N is the number of rows to copy (min(n, len(self))) and C is
            the number of columns, due to list comprehension and copying elements.
        """
        # Validate input `n`
        if not isinstance(n, int):
            raise TypeError(f"n must be an integer, got {type(n).__name__}")
        if n < 0:
            raise ValueError("n must be non-negative")

        rows_to_copy = min(n, len(self))
        # Why: `range` provides the correct sequence of indices for the head.
        return self._create_molder_from_indices(list(range(rows_to_copy)))

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def tail(self, n: int = 5) -> 'DataMolder':
        """
        Return a new DataMolder with the last `n` rows (immutable copy with validation).

        Description:
            This method creates an immutable copy of the current DataMolder instance
            containing only the last 'n' rows. It ensures data integrity through
            type and constraint validation, leveraging efficient internal data copying.

        Args:
            n (int): The number of rows to include from the end of the DataMolder.
                     Defaults to 5.

        Returns:
            DataMolder: A new DataMolder instance containing the last 'n' rows.

        Raises:
            TypeError: If `n` is not an integer.
            ValueError: If `n` is negative.

        Example of use:
            >>> dm = DataMolder([("id", int)])
            >>> dm.add_rows([(1,), (2,), (3,), (4,), (5,), (6,)])
            >>> tail_dm = dm.tail(3)
            >>> len(tail_dm)
            3

        Cost:
            O(N * C) where N is the number of rows to copy (min(n, len(self))) and C is
            the number of columns, due to list comprehension and copying elements.
        """
        # Validate input `n`
        if not isinstance(n, int):
            raise TypeError(f"n must be an integer, got {type(n).__name__}")
        if n < 0:
            raise ValueError("n must be non-negative")

        total_rows = len(self)
        start_index = max(0, total_rows - n)
        # Why: `range` provides the correct sequence of indices for the tail.
        return self._create_molder_from_indices(list(range(start_index, total_rows)))

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def copy(self) -> 'DataMolder':
        """Creates a shallow copy of the DataMolder instance.

        Description:
            This method provides a high-performance way to duplicate a DataMolder instance.
            For maximum efficiency, it creates a shallow copy. The header and other metadata
            are deep-copied to ensure schema independence, but the underlying lists of column
            data are shared between the original and the new instance.

            This means that if you modify a cell value in the copy, the change will be
            reflected in the original instance, and vice-versa. This design choice
            prioritizes speed and low memory consumption, avoiding the O(R*C) cost of a
            full deep copy, which can be substantial for large datasets.

        Args:
            None

        Returns:
            DataMolder: A new DataMolder instance that is a shallow copy of the original.

        Raises:
            None

        Example of use:
            >>> dm_original = DataMolder([("id", int), ("value", str)])
            >>> dm_original.add_row([1, "original"])
            >>>
            >>> # Create a low-cost, shallow copy
            >>> dm_copy = dm_original.copy()
            >>>
            >>> # Modifying a cell in the copy
            >>> dm_copy.update_cell(0, "value", "modified_in_copy")
            >>>
            >>> # The change is reflected in the original because the data lists are shared
            >>> print(f"Original's value: {dm_original.get_cell(0, 'value')}")
            Original's value: modified_in_copy

        Cost:
            The operation is very fast. The cost is primarily driven by copying metadata
            structures and lists of row/column states, approximately O(C + R + K), where C is
            the number of columns, R is the number of rows (for the _modified list), and K is
            the number of unique keys. It does not iterate over every data cell.
        """
        # Why: Use the `__new__` method to create a new instance without calling `__init__`,
        # which would reset the state. This is a standard pattern for custom copy implementations.
        cls = self.__class__
        new_molder = cls.__new__(cls)

        # Why: Create a shallow copy of the instance's dictionary. This copies references
        # to the top-level mutable objects like the _data dictionary and _modified list.
        new_molder.__dict__.update(self.__dict__)

        # Why: Deepcopy the header to ensure that schema modifications on the copy
        # (e.g., adding or removing a column) do not affect the original. The header's size is
        # small (related to C, not R), so this is an inexpensive but important operation for safety.
        new_molder.header = copy.deepcopy(self.header)

        # Why: Explicitly create shallow copies of the top-level mutable containers.
        # This prevents operations like `new_molder._data = {}` from affecting the original,
        # while still sharing the internal lists of data for performance.
        new_molder._data = self._data.copy()
        new_molder._key_set = self._key_set.copy()
        new_molder._modified = self._modified.copy()
        new_molder._bookmarks = self._bookmarks.copy()
        new_molder._locked_rows = self._locked_rows.copy()
        new_molder._locked_columns = self._locked_columns.copy()

        # Why: Computed column definitions contain functions and lists. A deepcopy is safer
        # to prevent cross-instance interference if these definitions were ever to be modified directly.
        # The performance impact is negligible as the number of computed columns is typically small.
        new_molder._computed_columns = copy.deepcopy(self._computed_columns)
        new_molder._source_column_dependents = copy.deepcopy(self._source_column_dependents)

        return new_molder

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def slice(self, start: Optional[int] = None, stop: Optional[int] = None, step: Optional[int] = None) -> 'DataMolder':
        """
        Return a new DataMolder with a slice of rows, similar to list slicing.

        Description:
            This method allows extracting a subset of rows from the DataMolder
            based on start, stop, and optional step indices, mimicking Python's
            list slicing behavior. It returns a new immutable DataMolder instance
            containing the selected rows.

        Args:
            start (Optional[int]): The starting index of the slice (inclusive).
                                   Defaults to 0 if None.
            stop (Optional[int]): The ending index of the slice (exclusive).
                                  Defaults to len(self) if None.
            step (Optional[int]): The step for the slice. Defaults to 1 if None.

        Returns:
            DataMolder: A new DataMolder instance containing the sliced rows.

        Raises:
            TypeError: If start, stop, or step are not integers or None.
            ValueError: If step is zero.

        Example of use:
            >>> dm = DataMolder([("value", int)])
            >>> dm.add_rows([(10,), (20,), (30,), (40,), (50,)])
            >>> slice_dm = dm.slice(1, 4)
            >>> len(slice_dm)
            3
            >>> dm_even = dm.slice(0, None, 2)
            >>> len(dm_even)
            3 # (10, 30, 50)

        Cost:
            O(N_sliced * C) where N_sliced is the number of rows in the resulting slice
            and C is the number of columns, due to iterating and copying elements.
        """
        # Validate input types
        if start is not None and not isinstance(start, int):
            raise TypeError(f"start must be an integer or None, got {type(start).__name__}")
        if stop is not None and not isinstance(stop, int):
            raise TypeError(f"stop must be an integer or None, got {type(stop).__name__}")
        if step is not None and not isinstance(step, int):
            raise TypeError(f"step must be an integer or None, got {type(step).__name__}")
        if step == 0:
            raise ValueError("step cannot be zero")

        # Create a slice object to correctly interpret indices and step
        slice_obj = slice(start, stop, step)

        # Generate the indices based on the slice object
        # Why: This leverages Python's built-in slice logic to correctly
        # handle positive/negative indices and steps for iteration.
        all_indices = list(range(len(self)))
        sliced_indices = all_indices[slice_obj]

        return self._create_molder_from_indices(sliced_indices)

    # --- Find and Replace Mechanism ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> 'DataMolder':
        """Filters rows based on a predicate, returning a new DataMolder instance."""
        new_molder = DataMolder(
            columns=[(c, self.header.get_type(c)) for c in self.columns],
            validate_on_change=self.validate_on_change
        )
        for i in range(len(self)):
            row = self.get_row(i)
            if predicate(row):
                new_molder.add_row(row)
        return new_molder

    # --- Locking Mechanism ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def lock_row(self, index: int):
        if not (0 <= index < len(self)): raise IndexError("Row index out of range.")
        self._locked_rows.add(index)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def unlock_row(self, index: int):
        self._locked_rows.discard(index)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def lock_column(self, column: str):
        if column not in self.header: raise ColumnNotFoundError(f"Column '{column}' not found.")
        self._locked_columns.add(column)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def unlock_column(self, column: str):
        self._locked_columns.discard(column)

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def lock_all_rows(self): self._all_rows_locked = True

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def unlock_all_rows(self): self._all_rows_locked = False

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top    
    def lock_all_columns(self): self._all_columns_locked = True

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def unlock_all_columns(self): self._all_columns_locked = False

    def is_row_locked(self, index: int) -> bool:
        if not (0 <= index < len(self)): raise IndexError("Row index out of range.")
        return self._all_rows_locked or index in self._locked_rows

    def is_column_locked(self, column: str) -> bool:
        if column not in self.header: raise ColumnNotFoundError(f"Column '{column}' not found.")
        return self._all_columns_locked or column in self._locked_columns

    # --- Cursor and Bookmarks ---
    def move_first(self) -> bool:
        if len(self) > 0:
            self._row_position = 0
            return True
        return False
    
    def move_last(self) -> bool:
        if len(self) > 0:
            self._row_position = len(self) - 1
            return True
        return False
    
    def move_next(self) -> bool:
        if self._row_position < len(self) - 1:
            self._row_position += 1
            return True
        return False
        
    def move_previous(self) -> bool:
        if self._row_position > 0:
            self._row_position -= 1
            return True
        return False
        
    @property
    def current_row(self) -> Optional[Dict[str, Any]]:
        if 0 <= self._row_position < len(self):
            return self.get_row(self._row_position)
        return None

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def add_bookmark(self, name: str):
        if self._row_position == -1:
            raise ValueError("Cannot add bookmark, cursor is not on a valid row.")
        self._bookmarks[name] = self._row_position

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def goto_bookmark(self, name: str):
        if name not in self._bookmarks:
            raise KeyError(f"Bookmark '{name}' not found.")
        self._row_position = self._bookmarks[name]

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def remove_bookmark(self, name: str):
        if name not in self._bookmarks:
            raise KeyError(f"Bookmark '{name}' not found.")
        del self._bookmarks[name]

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def list_bookmarks(self) -> Dict[str, int]:
        return self._bookmarks.copy()

    # --- DataMolders Blend ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def merge(self, other: 'DataMolder') -> None:
        """
        Appends all rows from another DataMolder into this instance after verifying
        that both have identical schemas (column names and types).

        Args:
            other (DataMolder): The other DataMolder whose rows to append.

        Raises:
            ValueError: If the column lists differ.
            TypeError: If any column has a mismatched data type.
        """
        # Verify identical column order and names
        if self.columns != other.columns:
            raise ValueError(
                f"Cannot merge DataMolder: column schemas differ."
                f"\nSelf columns: {self.columns}"
                f"\nOther columns: {other.columns}"
            )
        # Verify matching column types
        for col in self.columns:
            t_self = self.header.get_type(col)
            t_other = other.header.get_type(col)
            if t_self is not t_other:
                raise TypeError(
                    f"Type mismatch for column '{col}': "
                    f"{t_self.__name__} != {t_other.__name__}"
                )
        # Append all rows from `other` in a bulk operation
        # Using data_list to extract tuples of row values
        rows_to_add = other.data_list(include_header=False)
        self.append_rows(rows_to_add)

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def intersection(self, other: 'DataMolder') -> 'DataMolder':
        """
        Returns a new DataMolder containing rows present in both this instance and `other`.
        Raises if schemas differ.
        """
        # Verificar compatibilidad de esquema
        if self.columns != other.columns:
            raise ValueError(
                f"Cannot compute intersection: column schemas differ."
                f"\nSelf columns: {self.columns}"
                f"\nOther columns: {other.columns}"
            )
        for col in self.columns:
            if self.header.get_type(col) is not other.header.get_type(col):
                raise TypeError(
                    f"Type mismatch for column '{col}': "
                    f"{self.header.get_type(col).__name__} != {other.header.get_type(col).__name__}"
                )
        # Conjunto de filas comunes
        set_self = set(tuple(row) for row in self.data_list(include_header=False))
        set_other = set(tuple(row) for row in other.data_list(include_header=False))
        common = set_self & set_other
        # Crear nuevo DataMolder con filas comunes
        result = DataMolder(self.columns, [self.header.get_type(c) for c in self.columns])
        result.append_rows(list(common))
        return result

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top    
    def difference(self, other: 'DataMolder') -> 'DataMolder':
        """
        Returns a new DataMolder containing rows present in this instance but not in `other`.
        Raises if schemas differ.
        """
        # Verificar compatibilidad de esquema
        if self.columns != other.columns:
            raise ValueError(
                f"Cannot compute difference: column schemas differ."
                f"\nSelf columns: {self.columns}"
                f"\nOther columns: {other.columns}"
            )
        for col in self.columns:
            if self.header.get_type(col) is not other.header.get_type(col):
                raise TypeError(
                    f"Type mismatch for column '{col}': "
                    f"{self.header.get_type(col).__name__} != {other.header.get_type(col).__name__}"
                )
        # Conjunto de filas
        set_self = set(tuple(row) for row in self.data_list(include_header=False))
        set_other = set(tuple(row) for row in other.data_list(include_header=False))
        diff = set_self - set_other
        # Crear nuevo DataMolder con filas de diferencia
        result = DataMolder(self.columns, [self.header.get_type(c) for c in self.columns])
        result.append_rows(list(diff))
        return result

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def concatenate_by_row(self, other: 'DataMolder', validate_structure: bool = False) -> 'DataMolder':
        """
        Combines the rows of this DataMolder with another DataMolder instance.

        This method creates a new DataMolder instance containing all rows from
        the current instance followed by all rows from the `other` instance.
        It's designed for vertical concatenation (adding more rows).

        Args:
            other: The other DataMolder instance to concatenate_by_row.
            validate_structure: If True, checks if the headers (column names and types)
                                of both DataMolders are identical before concatenating.
                                If False, concatenation proceeds without strict schema validation,
                                potentially leading to data type inconsistencies if headers differ.

        Returns:
            DataMolder: A new DataMolder instance with combined rows.

        Raises:
            ValueError: If `validate_structure` is True and headers do not match.

        Examples:
            >>> dm1 = DataMolder([("id", int), ("name", str)])
            >>> dm1.add_rows([(1, "Alice"), (2, "Bob")])
            >>> dm2 = DataMolder([("id", int), ("name", str)])
            >>> dm2.add_rows([(3, "Charlie"), (4, "David")])
            >>> combined_dm = dm1.concatenate_by_row(dm2, validate_structure=True)
            >>> len(combined_dm)
            4
            >>> combined_dm[0]
            (1, 'Alice')
            >>> combined_dm[3]
            (4, 'David')
            
            # Example with structural mismatch (will raise ValueError if validate_structure=True)
            >>> dm_mismatch = DataMolder([("id", int), ("value", float)])
            >>> dm_mismatch.add_row((5, 10.5))
            >>> try:
            ...     dm1.concatenate_by_row(dm_mismatch, validate_structure=True)
            ... except ValueError as e:
            ...     print(e)
            Headers do not match. Cannot concatenate with validate_structure=True.

        Cost: O(M1 * N + M2 * N) where M1 and M2 are the number of rows in each DataMolder
            and N is the number of columns. This involves iterating through all data to copy.
        """
        if validate_structure and self._header != other._header:
            raise ValueError("Headers do not match. Cannot concatenate with validate_structure=True.")
        
        # Create a new DataMolder with the current header's definition
        new_DataMolder = DataMolder(
            [(col["name"], col["type"]) for col in self._header._columns],
            validators=self._header._validators,
            allow_none=self._header._allow_none,
            type_checking=self._header._type_checking,
            validate_on_change=self._validate_on_change
        )

        # Add all rows from the current DataMolder
        for i in range(len(self)):
            row = self[i]
            # When adding rows to the new DataMolder, ensure that
            # we respect the new schema, potentially adding None
            # for missing columns if `validate_structure` is False
            # and headers are different.
            processed_row = []
            for col_name in new_DataMolder.columns:
                try:
                    original_col_index = self._header.get_column_index(col_name)
                    processed_row.append(row[original_col_index])
                except ColumnNotFoundError:
                    # If the column exists in the new_DataMolder but not in the current row's schema,
                    # append default value or None based on allow_none.
                    processed_row.append(new_DataMolder._header.get_default(col_name))
            new_DataMolder.add_row(tuple(processed_row))


        # Add all rows from the other DataMolder
        for i in range(len(other)):
            row = other[i]
            processed_row = []
            for col_name in new_DataMolder.columns:
                try:
                    original_col_index = other._header.get_column_index(col_name)
                    processed_row.append(row[original_col_index])
                except ColumnNotFoundError:
                    processed_row.append(new_DataMolder._header.get_default(col_name))
            new_DataMolder.add_row(tuple(processed_row))

        self._save_version()

        return new_DataMolder

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def concatenate_by_column(self, other: 'DataMolder', validate_rows: bool = True) -> 'DataMolder':
        """
        Combines the columns of this DataMolder with another DataMolder instance.

        This method creates a new DataMolder instance by merging the columns
        of the current instance and the `other` instance. It's designed for
        horizontal concatenation (adding more columns).

        Args:
            other: The other DataMolder instance to concatenate columns from.
            validate_rows: If True, checks if both DataMolders have the same number of rows.
                        If False, the concatenation will proceed, filling missing rows
                        with `None` for the shorter DataMolder's columns.

        Returns:
            DataMolder: A new DataMolder instance with combined columns.

        Raises:
            ValueError: If `validate_rows` is True and row counts differ, or if duplicate
                        column names are found between the two DataMolders.

        Examples:
            >>> dm1 = DataMolder([("id", int), ("name", str)])
            >>> dm1.add_rows([(1, "Alice"), (2, "Bob")])
            >>> dm2 = DataMolder([("age", int), ("city", str)])
            >>> dm2.add_rows([(30, "NY"), (25, "LA")])
            >>> combined_dm = dm1.concatenate_by_column(dm2, validate_rows=True)
            >>> combined_dm.columns
            ['id', 'name', 'age', 'city']
            >>> combined_dm[0]
            (1, 'Alice', 30, 'NY')
            >>> combined_dm[1]
            (2, 'Bob', 25, 'LA')

            # Example with unequal row counts (will raise ValueError if validate_rows=True)
            >>> dm3 = DataMolder([("score", float)])
            >>> dm3.add_row((95.5,))
            >>> try:
            ...     dm1.concatenate_by_column(dm3, validate_rows=True)
            ... except ValueError as e:
            ...     print(e)
            DataMolders must have the same number of rows to concatenate columns
        
        Cost: O(M * (N1 + N2)) where M is the number of rows, N1 and N2 are the number
            of columns in each DataMolder.
        """

        # Ensure no columns in the current DataMolder are locked, as a new DataMolder is created
        # based on its structure and populated from both.
        for column_name in self.columns:
            if self.is_column_locked(column_name):
                raise PermissionError(f"Cannot concatenate: Column '{column_name}' in source DataMolder is locked.")


        # Check for column locks in both DataMolders
        for column_name in self.columns:
            if self.is_column_locked(column_name):
                raise PermissionError(f"Cannot concatenate columns: Column '{column_name}' in current DataMolder is locked.")
        for column_name in other.columns:
            if other.is_column_locked(column_name):
                raise PermissionError(f"Cannot concatenate columns: Column '{column_name}' in other DataMolder is locked.")
       
        # Check for common column names that would lead to duplication
        common_cols = set(self.columns).intersection(other.columns)
        if common_cols:
            raise ValueError(f"Found duplicate column names: {common_cols}")
            
        # Validate row counts if requested
        if validate_rows and len(self) != len(other):
            raise ValueError("DataMolders must have the same number of rows to concatenate columns")
            
        # Create new header combining both structures
        new_columns_def: List[Tuple[str, Type]] = []
        new_validators: Dict[str, Callable[[Any], bool]] = {}

        # Add columns from the current DataMolder
        for col_name in self.columns:
            new_columns_def.append((col_name, self._header.get_type(col_name)))
            validator = self._header.get_validator(col_name)
            if validator:
                new_validators[col_name] = validator
        
        # Add columns from the other DataMolder
        for col_name in other.columns:
            new_columns_def.append((col_name, other._header.get_type(col_name)))
            validator = other._header.get_validator(col_name)
            if validator:
                new_validators[col_name] = validator

        # Determine new allow_none based on both original DataMolders
        new_allow_none = self._header._allow_none and other._header._allow_none
        new_type_checking = self._header._type_checking and other._header._type_checking

        new_header = Header(
            new_columns_def,
            new_validators,
            new_allow_none,
            new_type_checking
        )
        
        # Create new DataMolder instance
        result = DataMolder(
            [(col["name"], col["type"], col["default"], col["required"], col["key"]) for col in new_header._columns],
            validators=new_header._validators,
            allow_none=new_header._allow_none,
            type_checking=new_header._type_checking,
            validate_on_change=self._validate_on_change
        )
        
        # Combine rows, handling potentially different row counts
        max_rows = max(len(self), len(other))
        for i in range(max_rows):
            new_row_values: List[Any] = []
            
            # Get values from current DataMolder
            if i < len(self):
                current_row = self[i]
                for col_name in self.columns:
                    new_row_values.append(current_row[self._header.get_column_index(col_name)])
            else:
                # If current DataMolder is shorter, fill with None for its columns
                for col_name in self.columns:
                    new_row_values.append(None) # Using None, assuming allow_none is true or will be handled by validation

            # Get values from other DataMolder
            if i < len(other):
                other_row = other[i]
                for col_name in other.columns:
                    new_row_values.append(other_row[other._header.get_column_index(col_name)])
            else:
                # If other DataMolder is shorter, fill with None for its columns
                for col_name in other.columns:
                    new_row_values.append(None) # Using None, assuming allow_none is true or will be handled by validation
            
            result.add_row(tuple(new_row_values))

        self._save_version()

        return result

    # --- Utility Methods ---

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def rename_column(self, old_column_name: str, new_column_name: str) -> None:
        """
        Renames an existing column in the DataMolder instance.

        Description:
            This method allows changing the name of a column, updating both the
            schema definition managed by the Header and the actual data storage.
            It ensures that all internal references to the column name are
            consistently updated.

        Args:
            old_column_name (str): The current name of the column to be renamed.
            new_column_name (str): The new name for the column.

        Raises:
            TypeError: If old_column_name or new_column_name are not strings.
            ColumnNotFoundError: If old_column_name does not exist.
            ValueError: If new_column_name already exists.
            PermissionError: If the column to be renamed is locked.

        Example of use:
            >>> dm = DataMolder([("id", int), ("name", str)])
            >>> dm.add_row([1, "Alice"])
            >>> dm.rename_column("name", "full_name")
            >>> dm.columns
            ['id', 'full_name']
            >>> dm.get_row(0)
            {'id': 1, 'full_name': 'Alice'}

        Cost:
            O(C) where C is the number of columns, due to updating internal dictionaries
            and list in Header and DataMolder.
        """
        if not isinstance(old_column_name, str) or not isinstance(new_column_name, str):
            raise TypeError("Column names must be strings.")

        if old_column_name not in self.header.columns:
            raise ColumnNotFoundError(f"Column '{old_column_name}' not found.")

        if new_column_name in self.header.columns:
            raise ValueError(f"New column name '{new_column_name}' already exists.")

        if self.is_column_locked(old_column_name):
            raise PermissionError(f"Cannot rename column '{old_column_name}': it is locked.")

        # --- Update Computed Column Definitions ---
        # Case 1: The column being renamed IS a computed column.
        if old_column_name in self._computed_columns:
            definition = self._computed_columns.pop(old_column_name)
            self._computed_columns[new_column_name] = definition
            # Update the reverse mapping to point to the new name.
            for dependents in self._source_column_dependents.values():
                if old_column_name in dependents:
                    dependents[dependents.index(old_column_name)] = new_column_name

        # Case 2: The column being renamed IS A SOURCE for a computed column.
        if old_column_name in self._source_column_dependents:
            # Move the list of dependents to the new source column name.
            self._source_column_dependents[new_column_name] = self._source_column_dependents.pop(old_column_name)
            # Update the source_columns list within each dependent computed column's definition.
            for func, sources in self._computed_columns.values():
                if old_column_name in sources:
                    sources[sources.index(old_column_name)] = new_column_name

        # Rename the column in the Header
        # Why: Delegate schema updates to the Header class, which is responsible
        # for managing column definitions and metadata.
        self.header._rename_column(old_column_name, new_column_name)

        # Update the actual data dictionary
        # Why: Reassigning the list reference from the old key to the new key
        # is an efficient O(1) operation for the data itself.
        self._data[new_column_name] = self._data.pop(old_column_name)

        # Update the column enumerate mapping
        # Why: This dictionary maps integer indices to column names and needs to be kept in sync.
        self._column_enumerate = {i: col for i, col in enumerate(self.header.columns)}

        # Update the cached key fields
        # Why: Key fields are a common lookup, so keeping this cache up-to-date
        # prevents stale data and unnecessary re-computations.
        self._key_fields = self.header.key_fields

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def cast_column_type(self,
                         column_identifier: Union[str, int],
                         new_type: Type,
                         force_cast: bool = False) -> None:
        """
        Description:
            Changes the data type of all values in a specified column.

        Description:
            This method attempts to cast each value in the column to the new type.
            If `force_cast` is True, any value that cannot be converted will be
            set to None. Otherwise, an error will be raised. The column's
            schema in the header is updated to reflect the new type.

        Args:
            column_identifier (Union[str, int]): The name or index of the column to modify.
            new_type (Type): The target data type to which the values will be cast.
            force_cast (bool): If True, conversion errors will result in a None value.
                               If False, errors will be raised. Defaults to False.

        Returns:
            None: The method modifies the DataMolder instance in-place.

        Raises:
            ColumnNotFoundError: If the specified column does not exist.
            PermissionError: If the specified column is locked.
            TypeError: If a value cannot be cast to the new type and `force_cast` is False.
            ValueError: If a value is inappropriate for the new type (e.g., converting 'abc' to int)
                        and `force_cast` is False.

        Example of use:
            >>> dm = DataMolder([('id', str), ('value', int)])
            >>> dm.add_rows([('1', 10), ('2', 20), ('3', 30)])
            >>> dm.cast_column_type('id', int)
            >>> print(dm.get_columns('id'))
            [1, 2, 3]
            >>> print(dm.header.get_type('id'))
            <class 'int'>

        Cost:
            O(N), where N is the number of rows in the DataMolder, as it
            must iterate through every item in the column.
        """
        # Why: Resolve the column identifier to a name first to ensure it exists
        # and to have a consistent way of accessing it.
        column_name = self._resolve_column_identifier(column_identifier)

        # Why: Check for locks before proceeding to prevent modification of protected data.
        if self.is_column_locked(column_name):
            raise PermissionError(
                f"Column '{column_name}' is locked and cannot be modified.")

        new_values = []
        original_values = self._data[column_name]

        # Why: Iterate through each value to attempt the type conversion individually.
        for i, value in enumerate(original_values):
            # Why: Skip None values as their type is ambiguous and casting is often not desired.
            if value is None:
                new_values.append(None)
                continue

            try:
                # Why: The core conversion logic. We attempt to call the new type
                # as a function on the value (e.g., int(value)).
                new_values.append(new_type(value))
            except (ValueError, TypeError) as e:
                # Why: Handle cases where the conversion is not possible.
                if force_cast:
                    new_values.append(None)
                else:
                    # Why: Raise a descriptive error to inform the user exactly where the failure occurred.
                    raise TypeError(
                        f"Could not cast value '{value}' (at row {i}) to type {new_type.__name__} "
                        f"in column '{column_name}'.") from e

        # Why: If a transformed column is a dependency, all dependent
        # computed columns must be fully recomputed.
        if column_name in self._source_column_dependents:
            for dependent_col in self._source_column_dependents[column_name]:
                self._recompute_column(dependent_col)

        # --- Update State ---
        # Why: Only update the internal state *after* all conversions have succeeded.
        # This prevents the DataMolder from being left in a partially modified, inconsistent state.

        # Update the data itself
        self._data[column_name] = new_values

        # Update the schema in the header
        self.header._types[column_name] = new_type

        # Why: The data has changed, so all rows should be marked as modified.
        self._modified = [True] * len(self)

        # Why: If validation is deferred, the new data must be re-validated.
        if not self.validate_on_change:
            self._is_validated = False

        self._save_version()

    @log_operation_time
    @log_function_call # Decorators are applied from bottom to top
    def validate_all(self) -> None:
        """
        Performs a full validation of all data currently stored in the DataMolder.

        This method is particularly useful when `validate_on_change` is set to `False`,
        allowing for deferred and batch validation.

        Raises:
            List[ValidationError]: A list of all validation errors found if any data
                                fails validation. If multiple errors occur, they
                                are collected and raised together for efficiency.

        Cost: O(num_rows * num_columns) as it iterates through all data cells.

        Example of use:
            >>> DataMolder_deferred = DataMolder([("id", int), ("name", str)], validate_on_change=False)
            >>> DataMolder_deferred.add_row((1, "Alice"))
            >>> DataMolder_deferred.add_row(("invalid_id", "Bob"))
            >>> try:
            ...     DataMolder_deferred.validate_all()
            ... except ValidationError as e:
            ...     print(e) # doctest: +SKIP
            Validation Errors:
            - Value for column 'id' must be of type <class 'int'>, got str. (Row 1, Column 'id')
            >>> DataMolder_deferred.is_validated
            True
        """
        validation_errors: List[str] = []
        for row_index in range(self._length):
            for col_def in self._header.columns_definition:
                column_name = col_def["name"]
                value = self._data[column_name][row_index]
                try:
                    self._header.validate_value(column_name, value)
                except ValidationError as e:
                    # Collect error messages with context
                    validation_errors.append(f"- {e} (Row {row_index}, Column '{column_name}')")
        
        if validation_errors:
            # Re-raise as a single ValidationError containing all messages
            raise ValidationError("Validation Errors:\n" + "\n".join(validation_errors))
        
        # If all validations pass, mark as validated
        self._is_validated = True

    @property
    def is_validated(self) -> bool:
        """
        Returns True if the DataMolder's data is currently considered validated,
        False otherwise. This flag is primarily managed when `validate_on_change`
        is False.

        Returns:
            bool: True if validated, False if not.
        """
        return self._is_validated
        
    def clear(self):
        """Removes all rows from the data."""
        self._data = {col: [] for col in self.columns}
        self._modified = []
        self._row_position = -1
        self._bookmarks.clear()

    def destroy(self):
        """
        Removes all rows and columns from the DataMolder.
        """
            
        self.header = Header([], None, True, True)
        self._column_enumerate = None

        self._data: Dict[str, List[Any]] = {col: [] for col in self.header.columns}
        self._modified: List[bool] = []
        
        self._row_position: int = -1
        self._bookmarks: Dict[str, int] = {}
        
        self._locked_rows: set[int] = set()
        self._locked_columns: set[str] = set()
        self._all_rows_locked: bool = False
        self._all_columns_locked: bool = False

    def log_entries(self):
        return OperationLog.log_entries()
    
    def __len__(self) -> int:
        """
        Counts the number of rows in the DataMolder instance.

        Returns:
            int: The total number of rows.
        """
        if hasattr(self, "_data"):
            return len(self._data[self.columns[0]]) if self.columns else 0
        else:
            return "<DataMolder (empty)>"
    
    def __getitem__(self, key: Union[int, slice]) -> Union[Tuple[Any, ...], List[Tuple[Any, ...]]]:
        """
        Description:
            Enables standard, predictable row-based indexing and slicing.

        Args:
            key (Union[int, slice]): The index or slice for row retrieval.

        Returns:
            Union[Tuple[Any, ...], List[Tuple[Any, ...]]]: A single row tuple or a list of row tuples.

        Raises:
            IndexError: If any row index is out of range.
            TypeError: If the key is not an integer or slice.

        Example of use:
            >>> single_row = DataMolder[5]
            >>> multiple_rows = DataMolder[10:20]

        Cost:
            - O(C) for a single row (integer key), where C is the number of columns.
            - O(S * C) for a slice, where S is the number of rows in the slice.
        """
        if isinstance(key, int):
            # Why: Allow for standard negative indexing.
            if key < 0:
                key += len(self)
            if not (0 <= key < len(self)):
                raise IndexError("Row index out of range.")
            
            # Why: A generator expression within `tuple()` is a concise and efficient
            # way to construct the row tuple.
            return tuple(self._data[col][key] for col in self.columns)

        if isinstance(key, slice):
            # return a cell.
            column_name = self.columns[key.stop]
            return self._data[column_name][key.start]
        
        raise TypeError("Index must be an integer or a slice.")  

    def __iter__(self) -> Iterator[Tuple[Any, ...]]:
        """
        Description:
            Returns an iterator over the rows in the DataMolder instance.

        Description:
            This implementation uses `zip` on the columnar data, which is a highly
            efficient, C-implemented way to iterate over rows without constructing
            each row tuple manually in a Python loop.

        Returns:
            Iterator[Tuple[Any, ...]]: An iterator over the rows as tuples.

        Example of use:
            >>> for row in DataMolder:
            ...     print(row)

        Cost:
            O(N * C) for a full iteration, but it's a lazy iterator, so the cost
            is incurred per row. The per-row creation is very fast.
        """
        # Why: `zip` on the column lists is the most performant way to iterate row-by-row
        # over columnar data. It avoids Python-level loops and the overhead of `__getitem__`.       
        return zip(*self._data.values())


    def __repr__(self) -> str:
        """
        Description:
            Provides a concise, developer-friendly string representation of the DataMolder object.

        Description:
            This method is called by the `repr()` built-in function and is primarily used
            for debugging. It returns a summary of the object's dimensions.

        Returns:
            str: A string showing the class name, number of rows, and number of columns.

        Example of use:
            >>> dm = DataMolder([('id', int)])
            >>> dm.add_row([1])
            >>> repr(dm)
            '<DataMolder (rows: 1, columns: 1)>'

        Cost:
            O(1), as it only retrieves pre-calculated counts.
        """
        if not isinstance(self.columns,str):
            if self.columns:
                num_rows = len(self)
                num_cols = len(self.columns)
                return f"<DataMolder (rows: {num_rows}, columns: {num_cols})>"
            else:
                return "<DataMolder (empty)>"
        else:
             return "<DataMolder (empty)>"
        
    def _repr_html_(self) -> str:
        """
        Description:
            Generates a rich HTML representation for display in environments like Jupyter Notebooks.

        Description:
            This method creates an HTML table that intelligently summarizes the data.
            For large datasets, it shows only the first and last few rows and columns,
            preventing the browser from being overloaded.

        Returns:
            str: An HTML string representing the DataMolder's data.

        Example of use:
            # In a Jupyter Notebook cell:
            dm = DataMolder.mockup(100, ['id', 'name', 'value'])
            dm

        Cost:
            O(display_rows * display_cols). The cost is proportional to the number
            of cells being displayed, not the total size of the dataset.
        """
        num_rows = len(self)
        num_cols = len(self.columns)

        if num_rows == 0:
            return f"<div><p><b>DataMolder</b> ({num_rows} rows x {num_cols} columns)</p><i>(empty)</i></div>"

        # --- Configuration for display ---
        max_rows_to_display = 20
        max_cols_to_display = 10
        head_rows = max_rows_to_display // 2
        tail_rows = max_rows_to_display - head_rows
        head_cols = max_cols_to_display // 2
        tail_cols = max_cols_to_display - head_cols

        # --- Determine which columns to display ---
        column_indices = list(range(num_cols))
        display_columns_indices = column_indices
        columns_truncated = False
        if num_cols > max_cols_to_display:
            columns_truncated = True
            display_columns_indices = (column_indices[:head_cols] +
                                       column_indices[-tail_cols:])

        # --- HTML and CSS Styling ---
        # Using a more modern and clean CSS style
        html = """
        <style>
            .dm-container { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; margin: 1em 0; }
            .dm-table { border-collapse: collapse; width: auto; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .dm-table th, .dm-table td { padding: 8px 12px; text-align: left; border: 1px solid #e0e0e0; }
            .dm-table th { background-color: #f7f7f7; font-weight: 600; }
            .dm-table tr:nth-child(even) { background-color: #fdfdfd; }
            .dm-table td.dm-ellipsis { text-align: center; color: #999; }
            .dm-caption { caption-side: bottom; text-align: right; font-size: 0.9em; color: #666; padding-top: 5px; }
        </style>
        """
        html += "<div class='dm-container'>"
        html += "<table class='dm-table'>"

        # --- Table Header ---
        html += "<thead><tr><th>(index)</th>"
        for i in display_columns_indices:
            html += f"<th>{self.columns[i]}</th>"
        if columns_truncated:
            html += "<th class='dm-ellipsis'>...</th>"
        html += "</tr></thead>"

        # --- Table Body ---
        html += "<tbody>"

        def generate_row_html(row_idx):
            row_html = f"<tr><td><b>{row_idx}</b></td>"
            for col_idx in display_columns_indices:
                value = self._data[self.columns[col_idx]][row_idx]
                # Safely escape HTML characters in value
                value_str = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                row_html += f"<td>{value_str}</td>"
            if columns_truncated:
                row_html += "<td class='dm-ellipsis'>...</td>"
            row_html += "</tr>"
            return row_html

        if num_rows <= max_rows_to_display:
            for i in range(num_rows):
                html += generate_row_html(i)
        else:
            # Head rows
            for i in range(head_rows):
                html += generate_row_html(i)

            # Ellipsis row
            ellipsis_colspan = len(display_columns_indices) + 1 + (1 if columns_truncated else 0)
            html += f"<tr><td class='dm-ellipsis' colspan='{ellipsis_colspan}'>...</td></tr>"

            # Tail rows
            for i in range(num_rows - tail_rows, num_rows):
                html += generate_row_html(i)

        html += "</tbody>"
        html += f"<caption class='dm-caption'>[{num_rows} rows x {num_cols} columns]</caption>"
        html += "</table></div>"
        return html

    # --- Pandas dataframe integration   ---

    def get_from_dataframe(
        self,
        dataframe: Any, # Use Any here as pd.DataFrame is not imported globally
        reset_datamolder: bool = False,
        allow_none: Optional[bool] = None, # Use Optional to allow explicit override or use existing
        type_checking: Optional[bool] = None,
        validate_on_change: Optional[bool] = None
    ) -> None:
        """
        Loads data from a Pandas DataFrame into the current DataMolder instance.

        Description:
            This method populates or repopulates the DataMolder instance with data
            from a given Pandas DataFrame. If the DataMolder is empty, it infers
            the schema from the DataFrame. If the DataMolder already has a schema,
            it performs a compatibility check (unless reset_datamolder is True).
            The 'pandas' library is imported locally within this method, making
            it an optional dependency for DataMolder.

        Args:
            dataframe (Any): The Pandas DataFrame to load. Type hint is Any
                             because pandas is an optional dependency.
            reset_datamolder (bool): If True, the existing data and schema of the
                                     DataMolder will be cleared before loading from
                                     the DataFrame. If False, the method attempts
                                     to append data if schema is compatible, or raises
                                     an error if schema exists and is incompatible.
                                     Defaults to False.
            allow_none (Optional[bool]): Overrides the DataMolder's allow_none setting
                                         for this load operation. If None, the DataMolder's
                                         current allow_none setting is used.
            type_checking (Optional[bool]): Overrides the DataMolder's type_checking setting
                                          for this load operation. If None, the DataMolder's
                                          current type_checking setting is used.
            validate_on_change (Optional[bool]): Overrides the DataMolder's validate_on_change
                                                 setting for this load operation. If None, the
                                                 DataMolder's current validate_on_change setting is used.

        Returns:
            None

        Raises:
            ImportError: If the 'pandas' library is not installed when this method is called.
            TypeError: If the input is not a pandas DataFrame.
            ValueError: If the DataFrame is empty and the DataMolder has no existing schema,
                        or if `reset_datamolder` is False and the DataFrame schema is
                        incompatible with the DataMolder's existing schema.

        Example of use:
            >>> import pandas as pd
            >>> dm = DataMolder()
            >>> df1 = pd.DataFrame({'id': [1, 2], 'name': ['A', 'B']})
            >>> dm.get_from_dataframe(df1)
            >>> dm.count_rows()
            2
            >>> df2 = pd.DataFrame({'id': [3, 4], 'name': ['C', 'D']})
            >>> dm.get_from_dataframe(df2) # Appends if compatible
            >>> dm.count_rows()
            4
            >>> df3 = pd.DataFrame({'value': [10, 20]})
            >>> # dm.get_from_dataframe(df3, reset_datamolder=True) # Clears and loads new data

        Cost: O(R * C) where R is the number of rows and C is the number of columns in the DataFrame,
              due to iterating through columns for schema inference/comparison and then through rows for data population.
        """
        try:
            import pandas as pd
            # Why: Import pandas here to make it an optional dependency.
            # This allows DataMolder to be used without pandas if this method is not called.
        except ImportError:
            raise ImportError(
                "The 'pandas' library is required to use the 'get_from_dataframe' method. "
                "Please install it using 'pip install pandas'."
            )

        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame.")

        if dataframe.empty:
            if not self.columns:
                raise ValueError("DataFrame is empty and DataMolder has no existing schema to infer from.")
            OperationLog.log("get_from_dataframe", "DataFrame is empty, no new rows added.")
            return

        # Determine effective settings for the load operation
        _allow_none = self.allow_none if allow_none is None else allow_none
        _type_checking = self.type_checking if type_checking is None else type_checking
        _validate_on_change = self.validate_on_change if validate_on_change is None else validate_on_change

        # Infer column definitions from DataFrame dtypes
        df_column_definitions = []
        for col_name, dtype in dataframe.dtypes.items():
            if pd.api.types.is_integer_dtype(dtype):
                col_type = int
            elif pd.api.types.is_float_dtype(dtype):
                col_type = float
            elif pd.api.types.is_bool_dtype(dtype):
                col_type = bool
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                col_type = datetime
            else:
                col_type = str
            df_column_definitions.append((col_name, col_type))

        if reset_datamolder:
            # Why: Clear existing data and schema if reset_datamolder is True.
            # This makes the DataMolder ready to be completely overwritten by the DataFrame.
            self.clear_data()
            self._set_schema(df_column_definitions, _allow_none, _type_checking, _validate_on_change)
            OperationLog.log("get_from_dataframe", "DataMolder reset and schema set from DataFrame.")
        elif not self.columns:
            # Why: If DataMolder is empty and not resetting, infer schema directly.
            self.clear_data() # Ensure data is clear, though should be if no columns
            self._set_schema(df_column_definitions, _allow_none, _type_checking, _validate_on_change)
            OperationLog.log("get_from_dataframe", "DataMolder was empty, schema set from DataFrame.")
        else:
            # Why: If DataMolder has an existing schema and not resetting, perform compatibility check.
            # This ensures that appended data matches the current structure.
            existing_columns_map = {name: type_ for name, type_ in self._column_definitions}
            dataframe_columns_map = {name: type_ for name, type_ in df_column_definitions}

            if set(existing_columns_map.keys()) != set(dataframe_columns_map.keys()):
                raise ValueError(
                    "DataFrame columns do not match existing DataMolder columns. "
                    "Use 'reset_datamolder=True' to overwrite."
                )

            for col_name, df_col_type in dataframe_columns_map.items():
                if existing_columns_map[col_name] != df_col_type:
                    raise TypeError(
                        f"Type mismatch for column '{col_name}': DataMolder expects "
                        f"{existing_columns_map[col_name].__name__}, DataFrame has {df_col_type.__name__}. "
                        "Use 'reset_datamolder=True' to overwrite."
                    )
            OperationLog.log("get_from_dataframe", "DataFrame schema is compatible with existing DataMolder schema.")

        # Append data from DataFrame rows
        # Why: Using itertuples(index=False) is an efficient way to get rows as tuples,
        # which can then be directly passed to append_rows for bulk insertion.
        # This avoids row-by-row iteration overhead in Python.
        rows_as_tuples = [tuple(row) for row in dataframe.itertuples(index=False)]
        if rows_as_tuples:
            self.append_rows(rows_as_tuples)
            OperationLog.log("get_from_dataframe", f"Successfully loaded {len(rows_as_tuples)} rows from DataFrame.")

    def put_into_dataframe(self) -> Any: # Use Any for pd.DataFrame return type
        """
        Converts the current DataMolder instance into a Pandas DataFrame.

        Description:
            This method transforms the column-oriented data stored within the
            DataMolder into a new Pandas DataFrame. This allows seamless
            transition of data from DataMolder to Pandas for further analysis
            or manipulation using Pandas' extensive capabilities.

        Args:
            None

        Returns:
            pd.DataFrame: A new Pandas DataFrame populated with the DataMolder's data.

        Raises:
            ImportError: If the 'pandas' library is not installed when this method is called.

        Example of use:
            >>> dm = DataMolder([('id', int), ('name', str)])
            >>> dm.append_row({'id': 1, 'name': 'Alice'})
            >>> dm.append_row({'id': 2, 'name': 'Bob'})
            >>> df = dm.put_into_dataframe()
            >>> print(df)
               id   name
            0   1  Alice
            1   2    Bob

        Cost: O(R * C) where R is the number of rows and C is the number of columns,
              due to reconstructing the DataFrame from column data.
        """
        try:
            import pandas as pd
            # Why: Import pandas here to make it an optional dependency.
            # This allows DataMolder to be used without pandas if this method is not called.
        except ImportError:
            raise ImportError(
                "The 'pandas' library is required to use the 'put_into_dataframe' method. "
                "Please install it using 'pip install pandas'."
            )

        if not self._column_definitions:
            OperationLog.log("put_into_dataframe", "DataMolder has no columns, returning empty DataFrame.")
            return pd.DataFrame()

        # Why: Directly passing self._data (a dict of lists/arrays) is the most efficient
        # way to construct a pandas DataFrame from column-oriented data.
        dataframe = pd.DataFrame(self._data)
        OperationLog.log("put_into_dataframe", f"Converted DataMolder with {len(self.columns)} columns and "
                                     f"{self.count_rows()} rows to Pandas DataFrame.")
        return dataframe

    # --- Data versioning   ---
        
    def _save_version(self) -> None:
        """Save current state as a new version."""
        # Create deep copies to ensure version independence
        data_copy = {col: list(values) for col, values in self._data.items()}
        key_set_copy = set(self._key_set)
        self._version_control.push_version(data_copy, key_set_copy)
        
    def _restore_version(self, version_data: Tuple[dict, set]) -> None:
        """Restore state from a version."""
        if version_data:
            self._data, self._key_set = version_data
            self._num_rows = len(next(iter(self._data.values()))) if self._data else 0
            
    def undo(self) -> bool:
        """
        Undo the last operation if possible.
        
        Returns:
            bool: True if undo was successful, False otherwise
        """
        version_data = self._version_control.undo()
        if version_data:
            self._restore_version(version_data)
            return True
        return False
        
    def redo(self) -> bool:
        """
        Redo the last undone operation if possible.
        
        Returns:
            bool: True if redo was successful, False otherwise
        """
        version_data = self._version_control.redo()
        if version_data:
            self._restore_version(version_data)
            return True
        return False
        
    def get_version(self, index: int) -> bool:
        """
        Restore a specific version by index.
        
        Args:
            index (int): Version index to restore
            
        Returns:
            bool: True if version was restored, False if index invalid
        """
        version_data = self._version_control.get_version(index)
        if version_data:
            self._restore_version(version_data)
            return True
        return False

    @log_operation_time
    @log_function_call
    def get_as_dict(self, key_index: int = 0) -> Dict[Any, Tuple[Any, ...]]:
        """
        Converts the DataMolder to a dictionary keyed by the specified column index.

        Args:
            key_index (int): The index of the column to use as keys. Defaults to 0.

        Returns:
            Dict[Any, Tuple[Any, ...]]: A dictionary where keys are values from the specified column,
                                         and values are the corresponding row tuples.
        """
        return {row[key_index]: row for row in self}

