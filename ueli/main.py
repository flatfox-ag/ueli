import click
import json
import utils


VERSION = '0.0.1'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
CONFIG_FILE_NAME = 'ueli.yaml'


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
@click.pass_context
def ueli(ctx):
    """
    Ueli the servant helps to build and deploy at flatfox.

    Run `ueli status` to check current configuration and `ueli init` to
    properly login to glcoud for this project.

    Usual workflow would be:

    \b
        ueli build
        ueli push
        ueli stage deploy
    """
    # Main entry point. We use the context object to store our configuration
    # so they are available to all other commands through context
    config = utils.load_config_file(filename=CONFIG_FILE_NAME)
    if not config:
        click.secho("No config file '{}' found".format(CONFIG_FILE_NAME), fg='red')
        ctx.abort()
    ctx.obj['config'] = config


@ueli.command()
@click.option('--details', is_flag=True, help='Show all configuration details')
@click.pass_context
def status(ctx, details):
    """
    Show basic configuration and local repository information.
    To e.g. check if the right configuration file was loaded. Prints a hole
    configuration dump with `--details`.
    """
    config = ctx.obj['config']
    click.secho("Project", fg='cyan')
    click.secho("Name: {}".format(config['project']), fg='green')
    click.secho("Image: {}".format(config['image']['name']), fg='green')

    branch, commit, clean = utils.get_git_info()
    click.secho("Repository", fg='cyan')
    click.secho("Branch: {}".format(branch), fg='green')
    click.secho("Commit: {}".format(commit), fg='green')
    click.secho("Clean: {}".format(clean), fg='green' if clean else 'yellow')

    click.secho("Gcloud", fg='cyan')
    click.secho("Project: {}".format(config['gcloud']['project']), fg='green')
    click.secho("Registry: {}".format(config['gcloud']['registry']), fg='green')

    # TODO:
    # - check container image names in usedBy are named like project
    # - production can only deploy latest master!

    if details:
        click.secho("Config File", fg='cyan')
        click.echo(json.dumps(config, indent=4))


@ueli.command()
@click.pass_context
def init(ctx):
    """
    Login to gcloud and set project.
    """
    config = ctx.obj['config']
    project = config['gcloud']['project']

    if click.confirm('Do you want to (re)login to gcloud too? (will open browser)'):
        utils.run_local('gcloud auth login')
        utils.run_local('gcloud auth application-default login')

    utils.run_local('gcloud config set project {}'.format(project))
    click.echo('Done!')


@ueli.command()
@click.pass_context
def build(ctx):
    """
    Build image from current branch.
    """
    config = ctx.obj['config']
    project = config['project']
    image = config['image']['name']
    branch, commit, clean = utils.get_git_info()

    # Repository needs to be clean to build. Otherwise the image can contain
    # uncommited changes.
    if not clean:
        click.secho("Repository is not clean, clean up first.", fg='red')
        ctx.abort()

    click.secho("Building image '{image}' from '{branch}' ({commit})".format(
                image=image, branch=branch, commit=commit), fg='cyan')
    click.confirm('Do you want to continue?', abort=True)

    # Build and tag local image
    build_tag = utils.get_build_tag(project=project, image=image, branch=branch, commit=commit)
    cmd = "docker build --quiet=true --tag {build_tag} {image}".format(build_tag=build_tag, image=image)
    click.echo('Building image: {}'.format(build_tag))
    utils.run_local(cmd)

    click.echo('Done!')


@ueli.command()
@click.pass_context
def push(ctx):
    """
    Push image to remote registry.
    """
    config = ctx.obj['config']
    project = config['project']
    image = config['image']['name']
    branch, commit, clean = utils.get_git_info()
    remote = '{registry}/{project}'.format(registry=config['gcloud']['registry'],
                                           project=config['gcloud']['project'])

    build_tag = utils.get_build_tag(project=project, image=image, branch=branch, commit=commit)
    click.secho("Pushing '{build_tag}' to '{remote}'".format(
                build_tag=build_tag, remote=remote), fg='cyan')
    click.confirm('Do you want to continue?', abort=True)

    # Add remote tag to local image
    remote_tag = '{remote}/{build_tag}'.format(remote=remote, build_tag=build_tag)
    cmd = 'docker tag {build_tag} {remote_tag}'.format(build_tag=build_tag, remote_tag=remote_tag)
    utils.run_local(cmd)

    # Push image to remote server
    cmd = 'gcloud docker -- push {remote_tag}'.format(remote_tag=remote_tag)
    click.secho('Pushing image: {remote_tag}'.format(remote_tag=remote_tag))
    utils.run_local(cmd)

    click.echo('Done!')


@ueli.command()
@click.confirmation_option(prompt='Are you sure you want to delete all docker images?')
def delete_images():
    """
    Delete all local docker images.
    """
    utils.run_local('docker rmi -f $(docker images -q)')


# =============================
# ENVIRONMENT SPECIFIC COMMANDS
# =============================


@click.group()
@click.option('--branch', prompt='Branch to create a stage environment for',
              default=lambda: utils.get_git_info()[0])
@click.pass_context
def stage(ctx, branch):
    """
    Execute commands on stage cluster using branch as namespace.
    """
    ctx.obj['environment'] = 'stage'
    ctx.obj['namespace'] = branch


ueli.add_command(stage)


@click.group()
@click.pass_context
def production(ctx):
    """
    Execute commands on production cluster in production namespace.
    """
    ctx.obj['environment'] = 'production'
    ctx.obj['namespace'] = 'production'

    # checks
    branch, commit, clean = utils.get_git_info()
    if not utils.commit_is_pushed(commit=commit):
        click.secho("No config file '{}' found".format(CONFIG_FILE_NAME), fg='red')
        ctx.abort()


ueli.add_command(production)


@click.command()
@click.pass_context
def set_credentials(ctx):
    """
    Setting the right gcloud cluster credentials for kubectl.
    """
    config = ctx.obj['config']
    environment = ctx.obj['environment']
    project = config['gcloud']['project']
    cluster = config['gcloud']['cluster']
    if type(cluster) is dict:
        cluster = config['gcloud']['cluster'][environment]
    cmd = 'gcloud container clusters get-credentials {cluster} --project={project}'.format(
        cluster=cluster, project=project)
    utils.run_local(cmd)


@click.command()
@click.pass_context
def create_namespace(ctx):
    """
    Creates a namespace if it doesn't exist already.
    """
    namespace = ctx.obj['namespace']
    cmd = 'kubectl get namespace -o name'
    namespaces = utils.run_local(cmd).split('\n')
    if 'namespace/{}'.format(namespace) not in namespaces:
        cmd = 'kubectl create namespace {}'.format(namespace)
        utils.run_local(cmd)


@click.command()
@click.option('--tag', prompt='Tag to deploy',
              default=lambda: utils.get_tag_name(*utils.get_git_info()[:2]))
@click.pass_context
def deploy(ctx, tag):
    """
    Deploy specific image tag.
    """
    ctx.invoke(set_credentials)
    ctx.invoke(create_namespace)

    config = ctx.obj['config']
    image = config['image']['name']
    targets = config['image']['usedBy']
    project = config['project']
    namespace = ctx.obj['namespace']
    remote = '{registry}/{project}'.format(registry=config['gcloud']['registry'],
                                           project=config['gcloud']['project'])

    image_name = utils.get_image_name(project=project, image=image)
    build_tag = '{image_name}:{tag}'.format(image_name=image_name, tag=tag)
    remote_tag = '{remote}/{build_tag}'.format(remote=remote, build_tag=build_tag)
    for deployment in targets:
        container_name = project
        cmd = ('kubectl --namespace={namespace} set image deployment/{deployment} '
               '{container_name}={remote_tag}'.format(
                   namespace=namespace,
                   deployment=deployment,
                   container_name=container_name,
                   remote_tag=remote_tag))
        click.secho(cmd)
        utils.run_local(cmd)


stage.add_command(deploy)
production.add_command(deploy)


@click.command()
@click.pass_context
def apply_services(ctx):
    """
    Apply k8s services.
    """
    ctx.invoke(set_credentials)
    config = ctx.obj['config']
    namespace = ctx.obj['namespace']
    for service in config['services']:
        cmd = ('kubectl --namespace={namespace} apply -f '
               'kubernetes/{service}/{service}-service.yaml'.format(
                   namespace=namespace,
                   service=service))
        click.secho(cmd)
        utils.run_local(cmd)


stage.add_command(apply_services)
production.add_command(apply_services)


@click.command()
@click.pass_context
def apply_deployments(ctx):
    """
    Apply k8s deployments.
    """
    ctx.invoke(set_credentials)
    config = ctx.obj['config']
    namespace = ctx.obj['namespace']
    for deployment in config['deployments']:
        cmd = ('kubectl --namespace={namespace} apply -f '
               'kubernetes/{deployment}/{deployment}-deployment.yaml'.format(
                   namespace=namespace,
                   deployment=deployment))
        click.secho(cmd)
        utils.run_local(cmd)


stage.add_command(apply_deployments)
production.add_command(apply_deployments)


def main():
    ueli(obj={})
