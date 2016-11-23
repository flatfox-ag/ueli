import os.path
import yaml
import subprocess
import click


def load_yaml_file(path):
    working_dir = os.path.abspath('.')
    yaml_file = os.path.join(working_dir, path)
    exists = os.path.exists(yaml_file)

    if exists:
        with open(yaml_file, 'r') as f:
            return yaml.load(f)

    return None


def get_git_info():
    """
    Returns the current git branch and short commit hash
    """
    branch = run_local('git rev-parse --abbrev-ref HEAD')
    commit = run_local('git rev-parse --short --verify {}'.format(branch))
    clean = int(run_local('git status --porcelain | wc -l')) < 1
    return branch, commit, clean


def get_build_tag(service, branch, commit, tag=None):
    """
    Constructs full build tag for a service. The build tag is of the
    form: {service}:{branch}.{commit} e.g.

        flatfox-crawler_webapp:feature-xy.982405a

    """
    tag_name = tag if tag else get_tag_name(branch=branch, commit=commit)
    return '{service}:{tag_name}'.format(service=service, tag_name=tag_name)


def get_tag_name(branch, commit):
    return '{branch}.{commit}'.format(branch=branch, commit=commit)


def get_config_name(service):
    return '{service}-config'.format(service=service)


def get_secret_name(service):
    return '{service}-secret'.format(service=service)


def run_local(cmd, output=True, verbose=False, execute=True):
    ctx = click.get_current_context()

    if verbose or ctx.obj['verbose']:
        click.secho(u'$ {}'.format(cmd), fg='magenta')

    if execute:
        if output:
            return subprocess.check_output(cmd, shell=True).strip()
        subprocess.call(cmd, shell=True)
