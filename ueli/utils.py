import os.path
import yaml
import click

from functools import update_wrapper

CONFIG_FILE_NAME = 'ueli.yaml'


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
            # TODO: look for specific things in yaml, do not just copy the
            #       hole thing...
            config = yaml.load(file)
            config['configFile'] = config_file
            return config

    return None


def pass_config(f):
    """
    Checks if config is set on the context object and passes it to the
    decorated function or aborts if not.

    If used together with @click.pass_context, wrap @pass_config around:

        @utils.pass_config
        @click.pass_context
        def example(ctx, config):
            pass

    """
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        config = ctx.obj['config']
        if not config:
            click.secho("no config file found ./{}".format(CONFIG_FILE_NAME),
                        fg='red', bold=True)
            ctx.abort()
        return ctx.invoke(f, config, *args, **kwargs)
    return update_wrapper(new_func, f)
