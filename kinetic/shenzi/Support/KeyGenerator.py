import os
import sys
import time
import random
from ConfigParser import ConfigParser

# Globals -----------------------------------------------------------------------------------------
RANDOM_KEY_MASK_LEN = 1024*1024

DEFAULT_MIN_TOKEN = 0
DEFAULT_MAX_TOKEN = 255
DEFAULT_RANDOM_SEED = 2718
DEFAULT_IGNORE_OUT_OF_KEYS = True
DEFAULT_USE_RETIRED_RANDOM = False

# -------------------------------------------------------------------------------------------------
# Helper Functions /Exception
# -------------------------------------------------------------------------------------------------
class KeyGeneratorException(Exception):
    """
    Define an exception for KeyGenerator.py
    """
    def __init__(self, value):
        self.value = "["+str(value).replace("\n",";")+"]"

    def __str__(self):
        return repr(self.value)

def parse_config_file(config_path):
    """
    Parse the key type and key specifier from a config file
    """
    # Get the complete path for the config file
    if '~' in config_path:
        config_path = os.path.extenduser(config_path)
    else:
        config_path = os.path.abspath(config_path)

    # Read in config file
    config = ConfigParser()
    success = config.read(config_path)
    if not success:
        raise KeyGeneratorException("Failed to Read Key Configuration File")
    key_type = config.get('Key Generator', 'Type')
    key_specifier = dict(config.items('Key Specifier'))
    return key_type, key_specifier

def create_keygen(pattern):
    """
    Given a string label of what pattern generator you want, will
    return the matching class so you can create an object from it.
    If given an unrecognized pattern it will return None
    """
    temp = {
        # Generate random or sequential fixed size keys
        'fixed':FixedKeyGenerator,

        # Generate keys that are dense lexicographic monotonic (sequential)
        # Or with uniform key-space probability (random)
        'lexicographic':LexicographicKeyGenerator,

        # Generate keys that have uniform size probability
        'random':RandomKeyGenerator,
        }

    # Return the pattern or raise an exception for unknown pattern
    if pattern.lower() not in temp.keys():
        raise KeyGeneratorException('Unrecognized key generator pattern: '+str(pattern)+'; Use \'fixed\', \'lexicographic\', or \'random\'')
    return temp[pattern.lower()]

# -------------------------------------------------------------------------------------------------
# Base Key Generator
# -------------------------------------------------------------------------------------------------
class BaseKeyGenerator(object):
    def __init__(self, key_specifier):
        self.type = "Base"
        self.original_specs = dict(key_specifier)

        # Required Fields
        self._random_percentage = float(key_specifier["random_percentage"])
        if hasattr(self, 'key_size'):
            self.max_key_size = int(self.key_size)
            self.min_key_size = int(self.key_size)
        else:
            self.max_key_size = int(key_specifier["max_key_size"])
            self.min_key_size = int(key_specifier["min_key_size"])

        # Optional Fields
        if "min_token" not in key_specifier:
            key_specifier["min_token"] = DEFAULT_MIN_TOKEN
        if "max_token" not in key_specifier:
            key_specifier["max_token"] = DEFAULT_MAX_TOKEN
        if "random_seed" not in key_specifier:
            key_specifier["random_seed"] = DEFAULT_RANDOM_SEED
        if "ignore_out_of_keys" not in key_specifier:
            key_specifier["ignore_out_of_keys"] = DEFAULT_IGNORE_OUT_OF_KEYS
        if "use_retired_random" not in key_specifier:
            key_specifier["use_retired_random"] = DEFAULT_USE_RETIRED_RANDOM
        if "start_key" not in key_specifier:
            key_specifier["start_key"] = chr(key_specifier["min_token"])*self.min_key_size
        self._ignore_out_of_keys = bool(key_specifier["ignore_out_of_keys"])
        self._use_retired_random = bool(key_specifier["use_retired_random"])
        self._min_token = int(key_specifier["min_token"])
        self._max_token = int(key_specifier["max_token"])
        self._start_key = str(key_specifier["start_key"])
        self.random_seed = int(key_specifier["random_seed"])
        self._random_percentage_generator = random.Random(self.random_seed)

        # Initialization
        self.current_key = self._start_key

        # Prep for Random Key Generation
        if self._random_percentage > 0:
            if not self._use_retired_random:
                self._offset_index = 0
            self._generate_random_key_mask()

    def get_next_key(self):
        """
        Override this method to handle key generation
        """
        pass

    def _generate_random_key(self, key_size):
        """
        Base random key generation, generate new random key mask once you're out of offsets
        """
        if self._use_retired_random:
            # Base random key generation, generate new random key mask once you've generated about
            # 90% of the length of the current random key mask
            if self.random_count > (RANDOM_KEY_MASK_LEN*0.90):
                self._generate_random_key_mask()
            x = self._random_token_generator.randint(0, RANDOM_KEY_MASK_LEN-key_size)
        else:
            if self._offset_index > (RANDOM_KEY_MASK_LEN-self.max_key_size):
                self._generate_random_key_mask()
                self._offset_index = 0
            x = self._offset_index
            self._offset_index += 1
        self.random_count += 1
        return self._RandomKeyMask[x:x+key_size]

    def _generate_random_key_mask(self):
        """
        Instead of generating a completely new string every time a random key mask is generated
        and continuously parsed. This allows for a repeatable pattern and improved efficiency
        """
        print "[KeyGenerator."+time.strftime('%Y/%m/%d_%H:%M:%S')+" | creating new random key mask]"
        self.random_count = 0
        self.random_seed += 1
        self._random_token_generator = random.Random(self.random_seed)
        token_list = [chr(x%256) for x in range(self._min_token, self._max_token+1)]
        self._RandomKeyMask = "".join([self._random_token_generator.choice(token_list) for n in range(RANDOM_KEY_MASK_LEN)])

# -------------------------------------------------------------------------------------------------
# Fixed Key Generator
# -------------------------------------------------------------------------------------------------
class FixedKeyGenerator(BaseKeyGenerator):
    def __init__(self, key_specifier):
        self.key_size = int(key_specifier["key_size"])
        super(FixedKeyGenerator, self).__init__(key_specifier)
        self.type = "Fixed"

    def get_next_key(self):
        """
        Generate a random or sequential key and return the new current key
        """
        if self._random_percentage_generator.random() < self._random_percentage:
            self._generate_random_key()
        else:
            self._generate_sequential_key()
        return self.current_key

    def _generate_random_key(self):
        self.current_key = super(FixedKeyGenerator, self)._generate_random_key(self.key_size)

    def _generate_sequential_key(self):
        """
        Generate the next sequential key with fixed size
        """
        init = self.current_key
        while (len(self.current_key) > 0) and (ord(self.current_key[-1]) == self._max_token):
            self.current_key = self.current_key[:-1]
        if len(self.current_key)==0:
            if self._ignore_out_of_keys:
                self.current_key = chr(self._min_token)*self.key_size
            else:
                raise KeyGeneratorException("Error: out of unique keys; reached Max Key "+init)
        else:
            self.current_key = self.current_key[:-1] + chr((ord(self.current_key[-1]) + 1)%256)
        self.current_key = self.current_key.ljust(self.key_size, chr(self._min_token))

# -------------------------------------------------------------------------------------------------
# Lexicographic Key Generator
# -------------------------------------------------------------------------------------------------
class LexicographicKeyGenerator(BaseKeyGenerator):
    def __init__(self, key_specifier):
        super(LexicographicKeyGenerator, self).__init__(key_specifier)
        self.type = "Lexicographic"
        if self._random_percentage != 0:
            self._LexKeySum = self._generate_lex_key_sum()

    def get_next_key(self):
        """
        Generate a random or sequential key and return the new current key
        """
        if self._random_percentage_generator.random() < self._random_percentage:
            self._generate_random_key()
        else:
            self._generate_sequential_key()
        return self.current_key

    def _generate_lex_key_sum(self):
        """
        Generates a list used to help generate random lexicographic keys
        """
        num_tokens = self._max_token - self._min_token + 1
        LexKeyWeight = [num_tokens**x for x in range(0, 4000)]
        LexKeySum = []
        n = 0
        for weight in LexKeyWeight:
            n += weight
            LexKeySum.append(n)
        return LexKeySum

    def _generate_random_key(self):
        """
        Generates a random key, from min_key_size to max_key_size tokens with tokens of
        min_token to max_token, inclusive, and with equal probability for all possible keys.
        """
        index = self.max_key_size
        random_target = self._random_token_generator.randint(self._LexKeySum[self.min_key_size], self._LexKeySum[self.max_key_size])
        while random_target < self._LexKeySum[index]:
            index -= 1
        self.current_key = super(LexicographicKeyGenerator, self)._generate_random_key(index+1)

    def _generate_sequential_key(self):
        """
        Generates the next key, a list of tokens, in lexicographic order after the specified key
        """
        init = self.current_key
        if len(self.current_key) < self.max_key_size:
            self.current_key = self.current_key + chr(self._min_token%256)
        else:
            while self.current_key[-1] == chr(self._max_token%256):
                self.current_key = self.current_key[:-1]
                if (len(self.current_key) < self.min_key_size) and not self._ignore_out_of_keys:
                    raise KeyGeneratorException("Error: out of unique keys; reached Max Key "+init)
                else:
                    self.current_key = self._start_key
                    return
            self.current_key = self.current_key[:-1]+chr((ord(self.current_key[-1])+1)%256)

# -------------------------------------------------------------------------------------------------
# Random Key Generator
# -------------------------------------------------------------------------------------------------
class RandomKeyGenerator(BaseKeyGenerator):
    def __init__(self, key_specifier):
        key_specifier['random_percentage'] = 1.0
        super(RandomKeyGenerator, self).__init__(key_specifier)
        self.type = "Random"

    def get_next_key(self):
        """
        Generates random keys with equal possibility for all key sizes
        """
        size = self._random_token_generator.randint(self.min_key_size, self.max_key_size)
        return super(RandomKeyGenerator, self)._generate_random_key(size)
