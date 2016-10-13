import os.path
import click
import json
import utils


VERSION = '0.0.1'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
def ueli():
    pass


@ueli.command()
@click.option('--details', is_flag=True, help='Show all config details')
def info(**kwargs):
    file, config = utils.load_config_file()
    if config:
        utils.print_info("project name", config['metadata']['name'])
        if kwargs['details']:
            utils.print_info("config file", file)
            print json.dumps(config, indent=4)
    else:
        print "no config file found './{}'".format(utils.CONFIG_FILE_NAME)


def main():
    ueli()


if __name__ == '__main__':
    ueli()
