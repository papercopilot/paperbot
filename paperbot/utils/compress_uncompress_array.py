# Filename: compress_uncompress_array.py

import numpy as np

def compress_array(array, zero_threshold=3):
    """
    Compresses a numpy array by replacing consecutive zeros with a compressed representation.

    Parameters:
    array (numpy.ndarray): The input array to be compressed.
    zero_threshold (int): The minimum number of consecutive zeros required to compress them.

    Returns:
    str: A semicolon-separated string representing the compressed array.
    """
    flattened = array.flatten()
    result = []
    zero_count = 0

    for num in flattened:
        if num == 0:
            zero_count += 1
        else:
            if zero_count > zero_threshold:
                result.append(f"0*{zero_count}")
            elif zero_count > 0:
                result.extend(['0'] * zero_count)
            result.append(str(num))
            zero_count = 0

    # Handle trailing zeros
    if zero_count > zero_threshold:
        result.append(f"0*{zero_count}")
    elif zero_count > 0:
        result.extend(['0'] * zero_count)

    return ';'.join(result)

def uncompress_string(compressed_string, shape):
    """
    Uncompresses a compressed string back into the original numpy array shape.

    Parameters:
    compressed_string (str): The compressed string representation of the array.
    shape (tuple): The shape of the original array.

    Returns:
    numpy.ndarray: The uncompressed array with the original shape.
    """
    elements = compressed_string.split(';')
    uncompressed = []

    for element in elements:
        if element.startswith('0*'):
            # Extract the number of consecutive zeros
            zero_count = int(element.split('*')[1])
            uncompressed.extend([0] * zero_count)
        else:
            uncompressed.append(int(element))

    # Convert the uncompressed list back to the original array shape
    return np.array(uncompressed).reshape(shape)

def example_usage():
    """
    Demonstrates the usage of compress_array and uncompress_string functions.
    """
    ts_array = np.array([
        [0, 0, 0, 0, 5, 6, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 8, 9, 0, 0, 0]
    ])  # A smaller example array, replace with your 100x100 array

    zero_threshold = 3
    compressed_string = compress_array(ts_array, zero_threshold)
    print("Compressed String:", compressed_string)

    original_shape = ts_array.shape  # The original shape of the array before compression
    uncompressed_array = uncompress_string(compressed_string, original_shape)
    print("Uncompressed Array:")
    print(uncompressed_array)

def test_compress_uncompress():
    """
    Unit test for compress_array and uncompress_string functions.
    """
    original_array = np.array([
        [0, 0, 0, 0, 5, 6, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 8, 9, 0, 0, 0]
    ])
    zero_threshold = 2
    compressed = compress_array(original_array, zero_threshold)
    uncompressed = uncompress_string(compressed, original_array.shape)
    assert np.array_equal(original_array, uncompressed), "Test failed: The uncompressed array does not match the original."
    print("Unit test passed.")

if __name__ == "__main__":
    example_usage()
    test_compress_uncompress()