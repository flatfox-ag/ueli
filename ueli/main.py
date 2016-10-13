import click
import json
import utils

VERSION = '0.0.1'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
@click.pass_context
def ueli(ctx):
    """
    Ueli the servant helps to build and deploy at flatfox.
    """
    # Main entry point. We use the context object to store our configuration
    # so they are available to all other commands through context
    ctx.obj['config'] = utils.load_config_file()


@ueli.command()
@click.option('--details', is_flag=True, help='Show all configuration details')
@utils.pass_config
def info(config, details):
    """
    Shows basic configuration information to e.g. check if the right
    configuration file was loaded. Prints a hole configuration dump with the
    `--details` option.
    """
    click.secho("project name: {}".format(config['metadata']['name']), fg='green')
    if details:
        click.echo(json.dumps(config, indent=4))


def main():
    ueli(obj={})
