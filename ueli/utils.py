import os.path
import yaml
import subprocess


def load_config_file(filename):
    """
    Tries to locate and load an ueli.yaml configuration file from the working
    directory, where ueli is called from. Returns a dictionary of settings.
    """
    working_dir = os.path.abspath('.')
    config_file = os.path.join(working_dir, filename)
    exists = os.path.exists(config_file)

    if exists:
        with open(config_file, 'r') as f:
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


def commit_is_pushed(commit):
    run_local('git fetch --all')
    return int(run_local('git branch -r --contains 3440850 | wc -l')) > 0


def get_build_tag(project, image, branch, commit):
    """
    Constructs full build tag for a given image. The build tag is of the
    form: {project}_{image}:{branch}.{commit} e.g.

        flatfox-crawler_webapp:feature-xy.982405a

    """
    return '{image_name}:{tag_name}'.format(
        image_name=get_image_name(project=project, image=image),
        tag_name=get_tag_name(branch=branch, commit=commit))


def get_image_name(project, image):
    return '{project}_{image}'.format(project=project, image=image)


def get_tag_name(branch, commit):
    return '{branch}.{commit}'.format(branch=branch, commit=commit)


def run_local(cmd):
    return (
        subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        .stdout
        .read()
        .strip())
