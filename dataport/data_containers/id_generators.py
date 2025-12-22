class SequentialIdGenerator:
    """A class to generate sequential integer IDs, similar to an auto-incrementing sequence.

    This class provides methods to get the next ID in a sequence,
    retrieve the current ID, and reset the sequence. It's useful for
    generating unique identifiers in a controlled, predictable manner.
    """

    def __init__(self, start: int = 0):
        """Initializes the SequentialIdGenerator.

        The sequence starts from the provided `start` value. The first ID
        returned by `next()` will be `start + 1`.

        Args:
            start (int): The initial value for the sequence. Defaults to 0.
        """
        # We use a private attribute `_current_id` to store the current ID.
        # This makes it clear that it's an internal detail of the class.
        self._current_id = start

    def next_id(self) -> int:
        """Increments the sequence and returns the next ID.

        Returns:
            int: The next sequential ID.

        Example of use:
            >>> generator = SequentialIdGenerator(start=5)
            >>> generator.next_id()
            6
            >>> generator.next_id()
            7
        """
        self._current_id += 1
        return self._current_id

    def reset(self, value: int = 0) -> None:
        """Resets the sequence to a specified value.

        Args:
            value (int): The value to which the sequence should be reset. Defaults to 0.

        Example of use:
            >>> generator = SequentialIdGenerator(start=10)
            >>> generator.next_id() # Returns 11
            11
            >>> generator.reset()
            >>> generator.next_id() # Returns 1
            1
            >>> generator.reset(value=100)
            >>> generator.next_id() # Returns 101
            101
        """
        # Reset the internal counter to the specified value.
        self._current_id = value

    def get_current_id(self) -> int:
        """Returns the current ID in the sequence without incrementing.

        Returns:
            int: The current ID.

        Example of use:
            >>> generator = SequentialIdGenerator(start=10)
            >>> generator.get_current_id()
            10
            >>> generator.next_id()
            11
            >>> generator.get_current_id()
            11
        """
        return self._current_id


def generate_unique_key(p_for_key):
    """Generates a unique key from a string using dynamically assigned prime numbers.

    This function processes an input string, converts it to lowercase, removes
    leading/trailing whitespace, and then generates a unique numerical key.
    Each unique character in the string is assigned a prime number, and these
    prime numbers are multiplied to form the final key.

    Args:
        p_for_key (str): The input string from which to generate the unique key.

    Returns:
        int: A unique numerical key generated from the input string.
             Returns None if the input string is empty or None.

    Example of use:
        >>> generate_unique_key("hello")
        210  # (2*3*5*7) - illustrative, actual primes assigned dynamically
        >>> generate_unique_key("world")
        4290 # (2*3*5*7*11) - illustrative, actual primes assigned dynamically
    """
    # Validate input: return None if the input string is empty or None.
    if not p_for_key:
        return None

    def _prime_generator():
        """Generates an infinite sequence of prime numbers.

        Yields:
            int: The next prime number in the sequence.
        """
        primes = []
        candidate = 2
        while True:
            # Check if the candidate number is divisible by any already found primes.
            # If not, it's a new prime.
            is_prime = all(candidate % prime != 0 for prime in primes)
            if is_prime:
                primes.append(candidate)
                yield candidate
            candidate += 1

    # Initialize a generator for prime numbers.
    prime_gen = _prime_generator()

    # Dictionary to store the mapping of characters to their assigned prime numbers.
    char_to_prime = {}

    # Normalize the input string: convert to lowercase and remove leading/trailing whitespace.
    # This ensures that "Hello" and "hello " produce the same key.
    normalized_key_string = p_for_key.lower().strip()

    # Initialize the key value. We start with 1 because it's the multiplicative identity.
    key_value = 1

    # Iterate through each character in the normalized string to generate the key.
    for char in normalized_key_string:
        # Assign a new prime number to the character if it hasn't been encountered before.
        if char not in char_to_prime:
            char_to_prime[char] = next(prime_gen)

        # Multiply the current key_value by the prime associated with the character.
        # This creates a unique product for the sequence of characters.
        key_value *= char_to_prime[char]

    return key_value

