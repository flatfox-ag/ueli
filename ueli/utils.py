import os.path
import yaml


CONFIG_FILE_NAME = 'ueli.yaml'


def print_info(name, value):
    left = '{}:'.format(name)
    print "{:<20}{}".format(left, value)


def load_config_file():
    """
    Tries to locate and load an ueli.yaml configuration file from the working
    directory, where ueli is called from. Returns a dictionary of settings.
    """
    working_dir = os.path.abspath('.')
    config_file = os.path.join(working_dir, CONFIG_FILE_NAME)
    exists = os.path.exists(config_file)

    if exists:
        with open(config_file, 'r') as file:
            return config_file, yaml.load(file)

    return None, None
