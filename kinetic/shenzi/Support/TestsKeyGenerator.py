"""
Tests - KeyGenerator
Usage: python TestsKeyGenerator.py
Purpose: A collection of tests to verify the various key generators are working as expected
"""
import time
import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
import KeyGenerator as KeyGenerator

# Globals -----------------------------------------------------------------------------------------
DEFAULT_NUM_KEYS = 1000000
DEFAULT_PRINT_SAMPLE = False

# -------------------------------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------------------------------
def run_all(num_keys=50000, print_sample=False):
    fixed_sequential(num_keys=num_keys, print_sample=print_sample)
    fixed_random(num_keys=num_keys, print_sample=print_sample)
    unique(num_keys=num_keys, print_sample=print_sample)
    lexicographic_sequential(num_keys=num_keys, print_sample=print_sample)
    lexicographic_random(num_keys=num_keys, print_sample=print_sample)
    random_size(num_keys=num_keys, print_sample=print_sample)

def _key_to_decimal(key):
    """ Converts a key to its decimal representation """
    key_len = len(key)
    decimal = 0
    i = 0
    for byte in map(ord, key):
        i += 1
        decimal += (byte << ((key_len-i)*8))
    return decimal

def _generate_keys(keyGen, num_keys):
    latency = []
    key_list = []

    try:
        for p in range(num_keys):
            t0 = time.time()
            key = keyGen.get_next_key()
            latency.append(time.time()-t0)
            key_list.append(key)
    except KeyGeneratorException as e:
        print keyGen.type+"| "+str(e)

    if len(latency) > 0:
        print "\tAve:%f Min:%f Max:%f"%((sum(latency)/len(latency)),
                                                     min(latency),
                                                     max(latency))
    else:
        print "\tDid not get any latency data"
    print "\tGenerated "+str(len(latency))+" Keys"
    return key_list

def _validate_key_lengths(key_list, min_size, max_size):
    for key in key_list:
        if not min_size <= len(key) <= max_size:
            print key
            return False, len(key)
    return True, None

# -------------------------------------------------------------------------------------------------
# Testing Functions
# -------------------------------------------------------------------------------------------------
# Fixed Sequential --------------------------------------------------------------------------------
def fixed_sequential(key_size=32, num_keys=DEFAULT_NUM_KEYS, print_sample=DEFAULT_PRINT_SAMPLE):
    # Create Key Gen
    key_specifier = {'random_percentage' : 0.0,
                     'key_size' : key_size}
    kg = KeyGenerator.FixedKeyGenerator(key_specifier)
    print ("Running "+kg.type).ljust(70, '-')

    # Generate Keys
    key_list = _generate_keys(kg, num_keys)

    # Post analyze
    temp = _validate_key_lengths(key_list, key_size, key_size)
    if not temp[0]:
        print "\tkey size error; out of bounds key size received: "+str(temp[1])

    diff_digits = len(str(_key_to_decimal(max(key_list)) - _key_to_decimal(min(key_list))))
    key_list_decimal = []
    for key in key_list:
        key_list_decimal.append(_key_to_decimal(key[-diff_digits:]))

    # Graph key sequence
    #   *For fixed sequential you should see a slow linear increase with
    #    occasional jumps for roll over (if you're not using full token range).
    plt.plot(key_list_decimal)
    plt.xlabel('Order of Appearance')
    plt.ylabel('ASCII Decimal Value of key')
    plt.title('Fixed Sequential: Decimal Sequence of Keys')
    plt.grid(True)
    plt.show()

    if print_sample:
        print "Sample:"
        print key_list[:min(len(key_list), 20)]

# Fixed Random ------------------------------------------------------------------------------------
def fixed_random(key_size=32, num_keys=DEFAULT_NUM_KEYS, print_sample=DEFAULT_PRINT_SAMPLE):
    key_specifier = {'random_percentage' : 1.0,
                     'key_size' : key_size}
    kg = KeyGenerator.FixedKeyGenerator(key_specifier)
    print ("Running "+kg.type).ljust(70, '-')

    # Generate Keys
    key_list = _generate_keys(kg, num_keys)

    # Post analyze
    temp = _validate_key_lengths(key_list, key_size, key_size)
    if not temp[0]:
        print "\tkey size error; out of bounds key size received: "+str(temp[1])

    key_token_distribution = [0]*256
    for key in key_list:
        for token in key:
            key_token_distribution[ord(token)] += 1

    # Get Histogram to check distribution of key tokens
    #     *For random the distribution should be even.
    #      If looking at sequential the distribution becomes more even
    #      as you cover more of the key-space.
    x = range(len(key_token_distribution))
    plt.bar(x, key_token_distribution)
    plt.xlabel('ASCII Decimal Value of Token')
    plt.ylabel('Number of Appearances')
    plt.title('Fixed Random: Distribution of key tokens')
    plt.grid(True)
    plt.show()

    if print_sample:
        print "Sample:"
        print key_list[:min(len(key_list), 20)]

# Unique ------------------------------------------------------------------------------------------
def unique(key_size=32, num_keys=DEFAULT_NUM_KEYS, print_sample=DEFAULT_PRINT_SAMPLE):
    key_specifier = {'random_percentage' : 1.0,
                     'ignore_out_of_keys' : False,
                     'key_size' : key_size}
    kg = KeyGenerator.UniqueKeyGenerator(key_specifier=key_specifier)
    print ("Running "+kg.type).ljust(70, '-')

    # Generate Keys
    key_list = _generate_keys(kg, num_keys)

    # Post analyze
    temp = _validate_key_lengths(key_list, key_size, key_size)
    if not temp[0]:
        print "\tkey size error; out of bounds key size received: "+str(temp[1])

    print "\t%d duplicate keys"%(len(key_list)-len(set(key_list)))

    if print_sample:
        print "Sample:"
        print key_list[:min(len(key_list), 20)]

# Lexicographic Sequential ------------------------------------------------------------------------
def lexicographic_sequential(min_key_size=1, max_key_size=32, num_keys=DEFAULT_NUM_KEYS, print_sample=DEFAULT_PRINT_SAMPLE):
    key_specifier = {'random_percentage' : 0.0,
                     'min_key_size' : min_key_size,
                     'max_key_size' : max_key_size}
    kg = KeyGenerator.LexicographicKeyGenerator(key_specifier)
    print ("Running "+kg.type).ljust(70, '-')

    # Generate Keys
    key_list = _generate_keys(kg, num_keys)

    # Post analyze
    temp = _validate_key_lengths(key_list, min_key_size, max_key_size)
    if not temp[0]:
        print "\tkey size error; out of bounds key size received: "+str(temp[1])

    key_token_distribution = [0]*256
    key_size_list = []

    for key in key_list:
        key_size_list.append(len(key))
        for token in key:
            key_token_distribution[ord(token)] += 1

    # Get Histogram to check distribution of key tokens
    #     *For lexicographic sequential the distribution becomes
    #      more even as you cover more of the key-space.
    x = range(len(key_token_distribution))
    plt.bar(x, key_token_distribution)
    plt.xlabel('ASCII Decimal Value of Token')
    plt.ylabel('Number of Appearances')
    plt.title('Lexicographic Sequential: Distribution of key tokens')
    plt.grid(True)
    plt.show()

    # Get Histogram to check distribution of sizes
    #     *Expect to see a much larger amount of max_size keys
    #      than any other key size.
    bins = []
    bins.extend(range(min_key_size, max_key_size+2))
    numpy_hist = plt.figure()
    plt.hist(key_size_list, bins)
    plt.xlabel('Key Size')
    plt.ylabel('Number of Keys')
    plt.title('Lexicographic Sequential: Distribution of key size')
    plt.grid(True)
    plt.show()

    if print_sample:
        print "Sample:"
        print key_list[:min(len(key_list), 20)]

# Lexicographic Random ----------------------------------------------------------------------------
def lexicographic_random(min_key_size=1, max_key_size=32, num_keys=DEFAULT_NUM_KEYS, print_sample=DEFAULT_PRINT_SAMPLE):
    key_specifier = {'random_percentage' : 1.0,
                     'ignore_out_of_keys' : True,
                     'min_key_size' : min_key_size,
                     'max_key_size' : max_key_size}
    kg = KeyGenerator.LexicographicKeyGenerator(key_specifier)
    print ("Running "+kg.type).ljust(70, '-')

    # Generate Keys
    key_list = _generate_keys(kg, num_keys)

    # Post analyze
    temp = _validate_key_lengths(key_list, min_key_size, max_key_size)
    if not temp[0]:
        print "\tkey size error; out of bounds key size received: "+str(temp[1])

    key_token_distribution = [0]*256
    key_size_list = []

    for key in key_list:
        key_size_list.append(len(key))
        for token in key:
            key_token_distribution[ord(token)] += 1

    # Get Histogram to check distribution of key tokens
    #     *For lexicographic random the distribution should be even.
    x = range(len(key_token_distribution))
    plt.bar(x, key_token_distribution)
    plt.xlabel('ASCII Decimal Value of Token')
    plt.ylabel('Number of Appearances')
    plt.title('Lexicographic Random: Distribution of key tokens')
    plt.grid(True)
    plt.show()

    # Get Histogram to check distribution of sizes
    #     *Expect to see a much larger amount of max_size keys
    #      than any other key size.
    bins = []
    bins.extend(range(min_key_size, max_key_size+2))
    numpy_hist = plt.figure()
    plt.hist(key_size_list, bins)
    plt.xlabel('Key Size')
    plt.ylabel('Number of Keys')
    plt.title('Lexicographic Random: Distribution of key size')
    plt.grid(True)
    plt.show()

    if print_sample:
        print "Sample:"
        print key_list[:min(len(key_list), 20)]

# Random Size -------------------------------------------------------------------------------------
def random_size(min_key_size=1, max_key_size=32, num_keys=DEFAULT_NUM_KEYS, print_sample=DEFAULT_PRINT_SAMPLE):
    key_specifier = {'min_key_size' : min_key_size,
                     'max_key_size' : max_key_size}
    kg = KeyGenerator.RandomKeyGenerator(key_specifier)
    print ("Running "+kg.type).ljust(70, '-')

    # Generate Keys
    key_list = _generate_keys(kg, num_keys)

    # Post analyze
    temp = _validate_key_lengths(key_list, min_key_size, max_key_size)
    if not temp[0]:
        print "\tkey size error; out of bounds key size received: "+str(temp[1])

    key_size_list = []
    for key in key_list:
        key_size_list.append(len(key))

    # Get Histogram to check distribution of sizes
    #    *Expect to see even distribution of key sizes
    bins = []
    bins.extend(range(min_key_size, max_key_size+2))
    numpy_hist = plt.figure()
    plt.hist(key_size_list, bins)
    plt.xlabel('Key Size')
    plt.ylabel('Number of Keys')
    plt.title('Random Key Size Generator: Distribution of key size')
    plt.grid(True)
    plt.show()

    if print_sample:
        print "Sample:"
        print key_list[:min(len(key_list), 20)]

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    run_all(num_keys=1000000)