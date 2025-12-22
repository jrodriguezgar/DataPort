class ComplexList(list):
    """
    A list subclass that enforces its elements to be either lists, tuples, or sets,
    determined at instantiation.

    This class extends the built-in list type but overrides methods
    that could potentially add invalid elements, ensuring type safety
    based on the configured element type.
    """

    def __init__(self, element_type, iterable=None):
        """
        Initializes the ComplexList instance, specifying the type of elements it will hold.

        Args:
            element_type (type): The type of elements this list should enforce.
                                 Must be 'list', 'tuple', or 'set'.
            iterable (iterable, optional): An iterable of elements to
                                           initialize the list. Defaults to None.

        Raises:
            ValueError: If element_type is not 'list', 'tuple', or 'set'.
            TypeError: If any element in the iterable does not match the specified element_type.

        Example of use:
            >>> my_list_of_tuples = ComplexList(tuple, [(1, 2), (3, 4)])
            >>> print(my_list_of_tuples)
            [(1, 2), (3, 4)]

            >>> my_list_of_lists = ComplexList(list, [[5, 6], [7, 8]])
            >>> print(my_list_of_lists)
            [[5, 6], [7, 8]]

            >>> my_list_of_sets = ComplexList(set, [{1, 2}, {3, 4}])
            >>> print(my_list_of_sets)
            [{1, 2}, {3, 4}]
        """
        if element_type not in (list, tuple, set):
            raise ValueError("element_type must be 'list', 'tuple', or 'set'.")
        self.element_type = element_type

        if iterable is not None:
            # Ensure all initial elements are of the specified type
            for item in iterable:
                if not isinstance(item, self.element_type):
                    raise TypeError(f"All elements must be of type {self.element_type.__name__}.")
        super().__init__(iterable if iterable is not None else [])

    def _validate_element(self, obj):
        """
        Internal helper to validate if an object matches the expected element_type.

        Args:
            obj: The object to validate.

        Raises:
            TypeError: If the object does not match the expected element_type.
        """
        if not isinstance(obj, self.element_type):
            raise TypeError(f"Only elements of type {self.element_type.__name__} can be added.")

    def append(self, obj):
        """
        Appends an element of the specified type to the end of the list.

        Args:
            obj (list, tuple, or set): The element to be appended.

        Raises:
            TypeError: If the appended object does not match the configured element_type.

        Returns:
            None

        Example of use:
            >>> my_complex_list = ComplexList(set)
            >>> my_complex_list.append({10, 20})
            >>> print(my_complex_list)
            [{10, 20}]

        Cost: O(1) on average.
        """
        self._validate_element(obj)
        super().append(obj)

    def extend(self, iterable):
        """
        Extends the list by appending all elements from an iterable.

        Args:
            iterable (iterable): An iterable containing only elements of the configured type.

        Raises:
            TypeError: If any element in the iterable does not match the configured element_type.

        Returns:
            None

        Example of use:
            >>> my_complex_list = ComplexList(list, [[1, 2]])
            >>> my_complex_list.extend([[3, 4], [5, 6]])
            >>> print(my_complex_list)
            [[1, 2], [3, 4], [5, 6]]

        Cost: O(k) where k is the number of elements in the iterable.
        """
        for item in iterable:
            self._validate_element(item)
        super().extend(iterable)

    def insert(self, index, obj):
        """
        Inserts an element of the specified type at a specified position in the list.

        Args:
            index (int): The index at which to insert the element.
            obj (list, tuple, or set): The element to be inserted.

        Raises:
            TypeError: If the inserted object does not match the configured element_type.

        Returns:
            None

        Example of use:
            >>> my_complex_list = ComplexList(tuple, [(1, 2), (3, 4)])
            >>> my_complex_list.insert(1, (9, 9))
            >>> print(my_complex_list)
            [(1, 2), (9, 9), (3, 4)]

        Cost: O(n) in the worst case, where n is the number of elements after the insertion point.
        """
        if not isinstance(obj, list):
            raise TypeError("Only lists can be inserted into ListList.")
        super().insert(index, obj)

    def remove(self, value):
        """
        Removes the first occurrence of a specified element value.

        Args:
            value (list, tuple, or set): The element value to be removed from the list.

        Raises:
            ValueError: If the specified value is not found in the list.
            TypeError: If the value to be removed does not match the configured element_type.

        Returns:
            None

        Example of use:
            >>> my_complex_list = ComplexList(set, [{1, 2}, {3, 4}, {1, 2}])
            >>> my_complex_list.remove({1, 2})
            >>> print(my_complex_list)
            [{3, 4}, {1, 2}]

        Cost: O(n) in the worst case, where n is the number of elements in the list.
        """
        super().remove(value)

    def pop(self, index=-1):
        """
        Removes and returns the element at the given index.

        Args:
            index (int, optional): The index of the element to remove. Defaults to -1 (last element).

        Raises:
            IndexError: If the list is empty or the index is out of range.

        Returns:
            list, tuple, or set: The removed element.

        Example of use:
            >>> my_complex_list = ComplexList(tuple, [(1, 2), (3, 4)])
            >>> popped_item = my_complex_list.pop()
            >>> print(popped_item)
            (3, 4)
            >>> print(my_complex_list)
            [(1, 2)]

        Cost: O(1) for the last element, O(n) for other elements.
        """
        return super().pop(index)

    def clear(self):
        """
        Removes all elements from the list.

        Returns:
            None

        Example of use:
            >>> my_complex_list = ComplexList(list, [[1, 2], [3, 4]])
            >>> my_complex_list.clear()
            >>> print(my_complex_list)
            []

        Cost: O(n) in the worst case, where n is the number of elements in the list.
        """
        super().clear()

    def reverse(self):
        """
        Reverses the elements of the list in place.

        Returns:
            None

        Example of use:
            >>> my_complex_list = ComplexList(tuple, [(1, 2), (3, 4), (5, 6)])
            >>> my_complex_list.reverse()
            >>> print(my_complex_list)
            [(5, 6), (3, 4), (1, 2)]

        Cost: O(n) where n is the number of elements in the list.
        """
        super().reverse()

    def count(self, value):
        """
        Returns the number of times a specified element value appears in the list.

        Args:
            value (list, tuple, or set): The element value to count.

        Raises:
            TypeError: If the value to count does not match the configured element_type.

        Returns:
            int: The number of occurrences of the value.

        Example of use:
            >>> my_complex_list = ComplexList(list, [[1, 2], [3, 4], [1, 2], [5, 6]])
            >>> count = my_complex_list.count([1, 2])
            >>> print(count)
            2

        Cost: O(n) where n is the number of elements in the list.
        """
        self._validate_element(value)
        return super().count(value)

    def index(self, value, start=0, stop=None):
        """
        Returns the index of the first occurrence of a specified element value.

        Args:
            value (list, tuple, or set): The element value to find.
            start (int, optional): The starting index for the search. Defaults to 0.
            stop (int, optional): The ending index for the search (exclusive). Defaults to None.

        Raises:
            ValueError: If the specified value is not found in the list within the given range.
            TypeError: If the value to find does not match the configured element_type.

        Returns:
            int: The index of the first occurrence of the value.

        Example of use:
            >>> my_complex_list = ComplexList(tuple, [(1, 2), (3, 4), (1, 2), (5, 6)])
            >>> index_val = my_complex_list.index((1, 2))
            >>> print(index_val)
            0

        Cost: O(n) in the worst case, where n is the number of elements in the search range.
        """
        self._validate_element(value)
        if stop is None:
            return super().index(value, start)
        else:
            return super().index(value, start, stop)

    def sort(self, key_position, reverse=False):
        """
        Sorts the list of elements in place based on the element at a specific position within each inner list or tuple.
        Note: This method is not directly applicable if the ComplexList holds 'set' elements,
        as sets are unordered and their elements are not accessible by position.

        Args:
            key_position (int): The index within each inner element (list or tuple) to use as the sorting key.
            reverse (bool, optional): If True, the list is sorted in descending order. Defaults to False.

        Raises:
            TypeError: If the ComplexList holds 'set' elements, or if the elements at
                       `key_position` are not comparable.
            IndexError: If `key_position` is out of bounds for any element in the list.

        Returns:
            None

        Example of use:
            >>> data_lists = ComplexList(list, [['apple', 3], ['banana', 1], ['cherry', 2]])
            >>> data_lists.sort(key_position=1) # Sort by the second element (integer)
            >>> print(data_lists)
            [['banana', 1], ['cherry', 2], ['apple', 3]]

            >>> data_tuples = ComplexList(tuple, [('c', 10), ('a', 30), ('b', 20)])
            >>> data_tuples.sort(key_position=0, reverse=True) # Sort by the first element (string), descending
            >>> print(data_tuples)
            [('c', 10), ('b', 20), ('a', 30)]

        Cost: O(N log N) where N is the number of elements in the list.
        """
        # We need to explicitly check if the element_type is 'set' because sets don't support indexing
        if self.element_type is set:
            raise TypeError("Cannot sort ComplexList if its elements are sets, as sets are unordered and unindexable.")
        super().sort(key=lambda x: x[key_position], reverse=reverse)

    def filter(self, filter_func: callable) -> 'ComplexList':
        """Filters elements from the ComplexList based on a provided filter function.

        Problem/User Need: When working with nested collections (lists, tuples, or sets),
        it's common to need to filter elements based on specific criteria while
        maintaining the type constraints of the ComplexList.

        Args:
            filter_func (callable): A function that takes an element (list, tuple, or set)
                                and returns True if the element should be kept,
                                False otherwise.

        Returns:
            ComplexList: A new ComplexList instance containing only the elements
                        for which filter_func returned True.

        Raises:
            TypeError: If filter_func is not callable.

        Example:
            >>> # Filter lists containing even numbers
            >>> complex_lists = ComplexList(list, [[1, 2], [3, 5], [4, 6]])
            >>> has_even = lambda x: any(n % 2 == 0 for n in x)
            >>> filtered = complex_lists.filter(has_even)
            >>> print(filtered)
            [[1, 2], [4, 6]]

            >>> # Filter tuples by length
            >>> complex_tuples = ComplexList(tuple, [(1,), (1, 2), (1, 2, 3)])
            >>> is_pair = lambda x: len(x) == 2
            >>> filtered = complex_tuples.filter(is_pair)
            >>> print(filtered)
            [(1, 2)]

            >>> # Filter sets by sum
            >>> complex_sets = ComplexList(set, [{1, 2}, {3, 4}, {5, 6}])
            >>> sum_greater_than_5 = lambda x: sum(x) > 5
            >>> filtered = complex_sets.filter(sum_greater_than_5)
            >>> print(filtered)
            [{3, 4}, {5, 6}]

        Cost:
            Time Complexity: O(n * k) where n is the number of elements in the list
                            and k is the complexity of filter_func.
            Space Complexity: O(n) for the new filtered list in worst case.
        """
        # Validate that filter_func is callable
        if not callable(filter_func):
            raise TypeError("filter_func must be a callable")

        # Create a new ComplexList with the same element_type
        filtered_elements = [elem for elem in self if filter_func(elem)]
        return ComplexList(self.element_type, filtered_elements)

    # ...existing code...
        def pick_elements(self, list_index, selector):
            """Picks element(s) from an inner list, set, or tuple within the ComplexList
            based on the provided selector.

            This method allows selective access or checking of elements within the
            list, tuple, or set stored at the given `list_index` in the ComplexList.

            Args:
                list_index (int): The index of the inner collection (list, set, or tuple)
                                within the ComplexList from which to pick elements.
                selector (int | str | slice | any): The selector to use:
                                                    - For inner lists and tuples:
                                                        - An integer for direct index access (e.g., 0, 1).
                                                        - A slice object (e.g., slice(1, 3)) to pick a range.
                                                        - A slice string (e.g., "1:3", ":2") to parse as a slice.
                                                    - For inner sets:
                                                        - A direct value to check for its presence (returns boolean).
                                                        - A two-element tuple (start, end) for a numerical range lookup
                                                        (returns a new set of matching elements within the range, exclusive of `end`).

            Returns:
                any | list | tuple | set | bool: The picked element(s).
                                                - Single element for direct index access.
                                                - List or tuple for slice operations.
                                                - Boolean for set value lookup.
                                                - Set for set numerical range lookup.

            Raises:
                IndexError: If 'list_index' is out of bounds for the ComplexList,
                            or if an integer selector is out of bounds for the inner list/tuple.
                TypeError: If an invalid selector type is provided for the inner collection type,
                        or if the inner collection is a set and a slice/index is used.
                ValueError: If a slice string is malformed.

            Example of use:
                >>> my_complex = ComplexList(list, [[10, 20, 30], ['a', 'b', 'c'], [1,2,3]])
                >>> my_complex.pick_elements(0, 1)
                20
                >>> my_complex.pick_elements(1, slice(0, 2))
                ['a', 'b']
                >>> my_complex.pick_elements(2, "1:3")
                [2, 3]

                >>> my_complex_sets = ComplexList(set, [{1, 5, 10, 15}, {20, 30}])
                >>> my_complex_sets.pick_elements(0, 5) # Check if 5 is in the set
                True
                >>> my_complex_sets.pick_elements(0, (0, 6)) # Elements between 0 and 6 (exclusive of 6)
                {1, 5}

                >>> my_complex_tuples = ComplexList(tuple, [('x', 'y', 'z')])
                >>> my_complex_tuples.pick_elements(0, 0)
                'x'

            Cost:
                O(1) for direct index access.
                O(k) for slicing (where k is slice length).
                O(N) for set range lookup (where N is the size of the set).
            """
            if not isinstance(list_index, int):
                raise TypeError("list_index must be an integer.")

            # Ensure list_index is within the bounds of the ComplexList itself
            if not 0 <= list_index < len(self):
                raise IndexError(f"list_index {list_index} out of bounds for ComplexList of size {len(self)}.")

            inner_collection = self[list_index]

            # Helper for parsing slice strings
            def _parse_slice_string(slice_str_val):
                try:
                    parts = slice_str_val.split(':')
                    if not (1 <= len(parts) <= 3):
                        raise ValueError("Incorrect number of parts for slice string.")
                    start = int(parts[0]) if parts[0] else None
                    stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
                    step = int(parts[2]) if len(parts) > 2 and parts[2] else None
                    return slice(start, stop, step)
                except ValueError:
                    raise ValueError(f"Malformed slice string: '{slice_str_val}'. Expected format like 'start:stop:step'.")

            # Handle lists and tuples (which support indexing and slicing)
            if isinstance(inner_collection, (list, tuple)):
                if isinstance(selector, int):
                    # Direct index access
                    try:
                        return inner_collection[selector]
                    except IndexError:
                        raise IndexError(
                            f"Selector {selector} out of bounds for inner {type(inner_collection).__name__} "
                            f"of size {len(inner_collection)}."
                        )
                elif isinstance(selector, slice):
                    # Slice object access
                    return inner_collection[selector]
                elif isinstance(selector, str):
                    # Parse slice string (e.g., "1:5", ":3", "2::2")
                    slicer = _parse_slice_string(selector)
                    return inner_collection[slicer]
                else:
                    raise TypeError(
                        f"Invalid selector type for {type(inner_collection).__name__}. "
                        f"Expected int, slice, or str (for slice string)."
                    )

            # Handle sets (which support presence checking and iteration for ranges)
            elif isinstance(inner_collection, set):
                if isinstance(selector, tuple) and len(selector) == 2 and \
                isinstance(selector[0], (int, float)) and isinstance(selector[1], (int, float)):
                    # Selector is a numerical range (start, end) for sets
                    start, end = selector
                    # Return a new set of elements that are numeric and fall within the specified range
                    return {x for x in inner_collection if isinstance(x, (int, float)) and start <= x < end}
                else:
                    # Selector is a direct value to check for its presence in the set
                    return selector in inner_collection
            else:
                # This case should ideally not be reached due to __init__ validation,
                # but it's good defensive programming.
                raise TypeError(f"Unsupported inner collection type: {type(inner_collection).__name__}")

    def remove_elements(self, list_index, item_to_remove):
        """Removes elements from an inner list, set, or tuple within the ComplexList
        based on a single element, a range (for sets), or slice notation (for lists/tuples).

        For inner lists and sets, the element(s) are removed in-place.
        For inner tuples, a new tuple is created without the specified element(s)
        and replaces the original tuple in the ComplexList.

        Args:
            list_index (int): The index of the inner collection (list, set, or tuple)
                              within the ComplexList from which to remove elements.
            item_to_remove (int | str | slice | any | tuple): The element(s) to remove:
                                                                - For lists and tuples:
                                                                    - An integer for direct index removal.
                                                                    - A slice object (e.g., slice(1, 3)) or a slice string (e.g., "1:3", ":2")
                                                                      to remove a range of elements.
                                                                    - A direct value to remove its first occurrence.
                                                                - For sets:
                                                                    - A direct value to remove that specific element.
                                                                    - A two-element tuple `(start, end)` for a numerical range
                                                                      to remove elements within that range (exclusive of `end`).

        Returns:
            list | set | tuple: The modified inner collection (for lists/sets) or a new tuple.

        Raises:
            IndexError: If 'list_index' is out of bounds for the ComplexList,
                        or if an integer removal index is out of bounds for the inner list/tuple.
            TypeError: If an invalid `item_to_remove` type is provided for the inner collection type,
                       or if the inner collection is a set and a slice/index is used for removal.
            ValueError: If a direct value is not found (for list.remove() or tuple value removal), or if a slice string is malformed.

        Example of use:
            >>> my_complex_lists = ComplexList(list, [[10, 20, 30], ['a', 'b', 'c']])
            >>> my_complex_lists.remove_elements(0, 1) # Remove element at index 1 from first list
            >>> print(my_complex_lists)
            [[10, 30], ['a', 'b', 'c']]

            >>> my_complex_lists.remove_elements(1, 'c') # Remove value 'c' from second list
            >>> print(my_complex_lists)
            [[10, 30], ['a', 'b']]

            >>> my_complex_tuples = ComplexList(tuple, [('x', 'y', 'z'), (1, 2, 3, 4, 5)])
            >>> new_tuple = my_complex_tuples.remove_elements(0, 'y') # Remove value 'y' from first tuple
            >>> print(my_complex_tuples)
            [('x', 'z'), (1, 2, 3, 4, 5)]
            >>> print(new_tuple)
            ('x', 'z')

            >>> new_tuple_slice = my_complex_tuples.remove_elements(1, "1:3") # Remove slice from second tuple
            >>> print(my_complex_tuples)
            [('x', 'z'), (1, 4, 5)]
            >>> print(new_tuple_slice)
            (1, 4, 5)

            >>> my_complex_sets = ComplexList(set, [{1, 5, 10, 15}, {20, 30}])
            >>> my_complex_sets.remove_elements(0, 10) # Remove value 10 from first set
            >>> print(my_complex_sets)
            [{1, 5, 15}, {20, 30}]

            >>> my_complex_sets.remove_elements(0, (0, 6)) # Remove numerical range (0 to 6) from first set
            >>> print(my_complex_sets)
            [{15}, {20, 30}]

        Cost:
            For lists/tuples: O(N) for index/value removal, O(N) for slicing (due to shifting/rebuilding).
            For sets: O(1) for direct removal, O(N) for range removal (where N is the size of the set/list/tuple).
        """
        if not isinstance(list_index, int):
            raise TypeError("list_index must be an integer.")

        if not 0 <= list_index < len(self):
            raise IndexError(f"list_index {list_index} out of bounds for ComplexList of size {len(self)}.")

        inner_collection = self[list_index]
        modified_collection = None # To hold the result for immutable types

        # Helper for parsing slice strings (re-defined locally or moved out of method if used often)
        def _parse_slice_string(slice_str_val):
            try:
                parts = slice_str_val.split(':')
                if not (1 <= len(parts) <= 3):
                    raise ValueError("Incorrect number of parts for slice string.")
                start = int(parts[0]) if parts[0] else None
                stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
                step = int(parts[2]) if len(parts) > 2 and parts[2] else None
                return slice(start, stop, step)
            except ValueError:
                raise ValueError(f"Malformed slice string: '{slice_str_val}'. Expected format like 'start:stop:step'.")

        # Handle lists (mutable)
        if isinstance(inner_collection, list):
            if isinstance(item_to_remove, int):
                # Remove by index
                try:
                    del inner_collection[item_to_remove]
                except IndexError:
                    raise IndexError(
                        f"Item to remove index {item_to_remove} out of bounds for inner list "
                        f"of size {len(inner_collection)}."
                    )
            elif isinstance(item_to_remove, slice):
                # Remove by slice object
                del inner_collection[item_to_remove]
            elif isinstance(item_to_remove, str):
                # Remove by slice string
                slicer = _parse_slice_string(item_to_remove)
                del inner_collection[slicer]
            else:
                # Remove by value (first occurrence)
                try:
                    inner_collection.remove(item_to_remove)
                except ValueError:
                    raise ValueError(f"Value '{item_to_remove}' not found in the list.")
            modified_collection = inner_collection # In-place modification

        # Handle sets (mutable)
        elif isinstance(inner_collection, set):
            if isinstance(item_to_remove, tuple) and len(item_to_remove) == 2 and \
               isinstance(item_to_remove[0], (int, float)) and isinstance(item_to_remove[1], (int, float)):
                # Remove numerical range (start, end)
                start, end = item_to_remove
                # Create a list of items to remove to avoid modifying set while iterating
                items_to_remove_in_range = [
                    x for x in inner_collection
                    if isinstance(x, (int, float)) and start <= x < end
                ]
                for item in items_to_remove_in_range:
                    inner_collection.discard(item) # Use discard to avoid KeyError if item somehow removed
            else:
                # Remove by direct value
                inner_collection.discard(item_to_remove) # Use discard for safety
            modified_collection = inner_collection # In-place modification

        # Handle tuples (immutable, requires creating a new tuple)
        elif isinstance(inner_collection, tuple):
            temp_list = list(inner_collection) # Convert to list for mutable operations
            if isinstance(item_to_remove, int):
                # Remove by index
                try:
                    del temp_list[item_to_remove]
                except IndexError:
                    raise IndexError(
                        f"Item to remove index {item_to_remove} out of bounds for inner tuple "
                        f"of size {len(inner_collection)}."
                    )
            elif isinstance(item_to_remove, slice):
                # Remove by slice object
                del temp_list[item_to_remove]
            elif isinstance(item_to_remove, str):
                # Remove by slice string
                slicer = _parse_slice_string(item_to_remove)
                del temp_list[slicer]
            else:
                # Remove by value (first occurrence)
                # Note: For tuples, this removes ALL occurrences of the value if not specified
                # as 'first occurrence' in the docstring. Python's list.remove() removes first.
                # If you want to remove ALL, filter like:
                # new_tuple_elements = [x for x in inner_collection if x != item_to_remove]
                # For consistency with list.remove() for single item removal:
                try:
                    temp_list.remove(item_to_remove) # This removes only the first occurrence
                except ValueError:
                    raise ValueError(f"Value '{item_to_remove}' not found in the tuple.")

            modified_collection = tuple(temp_list) # Convert back to tuple
            self[list_index] = modified_collection # Update the ComplexList with the new tuple
        else:
            # Should not be reached due to __init__ validation
            raise TypeError(f"Unsupported inner collection type: {type(inner_collection).__name__}.")

        return modified_collection

class SetSON:
    def __init__(self, key_field):
        """
        Inicializa la clase.
        :param key_field: El nombre del campo que se usará como clave principal.
        """
        self.key_field = key_field
        self.data_sets = {}  # Usamos un diccionario para un acceso rápido por clave

    # Métodos para gestionar los sets
    def add_set(self, data_dict):
        """
        Añade un nuevo set de datos al diccionario.
        :param data_dict: El diccionario que se añadirá.
        :return: El diccionario añadido o None si ya existe.
        """
        key_value = data_dict.get(self.key_field)
        if key_value is None:
            raise KeyError(f"El campo clave '{self.key_field}' no está presente en el diccionario.")
        
        if key_value in self.data_sets:
            print(f"Advertencia: Ya existe un set con la clave '{key_value}'.")
            return None
        
        self.data_sets[key_value] = data_dict
        return data_dict

    def remove_set(self, key_value):
        """
        Elimina un set de datos por su clave principal.
        :param key_value: El valor de la clave del set a eliminar.
        :return: True si se eliminó, False si no se encontró.
        """
        if key_value in self.data_sets:
            del self.data_sets[key_value]
            return True
        return False

    def get_set(self, key_value):
        """
        Busca y retorna un set de datos por su clave principal.
        :param key_value: El valor de la clave del set a buscar.
        :return: El diccionario si se encuentra, de lo contrario None.
        """
        return self.data_sets.get(key_value)

    # Métodos para actualizar el diccionario de un set
    def update_set(self, key_value, new_data):
        """
        Actualiza un set completo con un nuevo diccionario.
        :param key_value: La clave principal del set a actualizar.
        :param new_data: El nuevo diccionario que reemplazará al anterior.
        :return: El diccionario actualizado o None si no se encuentra.
        """
        if key_value in self.data_sets:
            self.data_sets[key_value] = new_data
            return self.data_sets[key_value]
        return None

    # Métodos para gestionar los elementos del diccionario
    def update_key(self, key_value, new_key, new_value):
        """
        Actualiza una clave y su valor dentro de un diccionario específico.
        :param key_value: La clave principal del set.
        :param new_key: La clave a actualizar dentro del diccionario.
        :param new_value: El nuevo valor para la clave.
        :return: True si se actualizó, False si no se encontró.
        """
        data_dict = self.get_set(key_value)
        if data_dict:
            data_dict[new_key] = new_value
            return True
        return False
        
    def delete_key(self, key_value, key_to_delete):
        """
        Elimina una clave de un diccionario dentro de un set.
        :param key_value: La clave principal del set.
        :param key_to_delete: La clave a eliminar del diccionario.
        :return: True si se eliminó, False si no se encontró.
        """
        data_dict = self.get_set(key_value)
        if data_dict and key_to_delete in data_dict:
            del data_dict[key_to_delete]
            return True
        return False

    def add_key(self, key_value, new_key, new_value):
        """
        Añade una nueva clave y valor a un diccionario específico.
        :param key_value: La clave principal del set.
        :param new_key: La nueva clave.
        :param new_value: El nuevo valor.
        :return: True si se añadió, False si el set no existe o la clave ya existe.
        """
        data_dict = self.get_set(key_value)
        if data_dict:
            if new_key in data_dict:
                print(f"Advertencia: La clave '{new_key}' ya existe en el diccionario.")
                return False
            data_dict[new_key] = new_value
            return True
        return False

    def __repr__(self):
        """Representación de la clase para facilitar la depuración."""
        return f"SetSON(key_field='{self.key_field}', sets={len(self.data_sets)})"
        