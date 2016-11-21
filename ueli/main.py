import click
import json
from ueli import utils


VERSION = '0.0.1'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
CONFIG_FILE_NAME = 'ueli.yaml'


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
@click.option('-v', '--verbose', is_flag=True, help='Enables verbose mode')
@click.pass_context
def ueli(ctx, verbose):
    """
    Ueli the servant helps to build and deploy at flatfox.

    Run `ueli status` to check current configuration and `ueli init` to
    properly login to glcoud for this project.

    Usual workflow would be:

    \b
        ueli build
        ueli push
        ueli deploy stage1 branch-xy

    Create new environment:

    \b
        ueli apply stage2
        ueli config stage2
        ueli deploy stage2 branch-xy
    """
    # Main entry point. We use the context object to store our configuration
    # so they are available to all other commands through context
    config = utils.load_yaml_file(path=CONFIG_FILE_NAME)
    if not config:
        click.secho("No config file '{}' found".format(CONFIG_FILE_NAME), fg='red')
        ctx.abort()
    ctx.obj['config'] = config
    ctx.obj['verbose'] = verbose


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
    click.secho("Service", fg='cyan')
    click.secho(config['service'], fg='green')

    click.secho("Gcloud", fg='cyan')
    click.secho("Project: {}".format(config['gcloud']['project']), fg='green')
    click.secho("Registry: {}".format(config['gcloud']['registry']), fg='green')
    click.secho("Cluster: {}".format(config['gcloud']['cluster']), fg='green')

    click.secho("Repository Status", fg='cyan')
    branch, commit, clean = utils.get_git_info()
    click.secho("Current Branch: {}".format(branch), fg='green')
    click.secho("Last Commit: {}".format(commit), fg='green')
    click.secho("Clean: {}".format(clean), fg='green' if clean else 'yellow')

    if details:
        click.secho("Config File", fg='cyan')
        click.echo(json.dumps(config, indent=4))


@ueli.command()
@click.pass_context
def init(ctx):
    """
    Login to gcloud and set project.

    TODO (silvan): how to handle service account for e.g. CI?
    """
    config = ctx.obj['config']
    gcloud_project = config['gcloud']['project']

    if click.confirm('Do you want to (re)login to gcloud too? (will open browser)'):
        utils.run_local('gcloud auth login')
        utils.run_local('gcloud auth application-default login')

    utils.run_local('gcloud config set project {}'.format(gcloud_project))

    click.echo('Done!')


@ueli.command()
@click.option('--force', is_flag=True, help='Froce build, ignore dirty git.')
@click.pass_context
def build(ctx, force):
    """
    Build image from current branch.
    """
    config = ctx.obj['config']
    verbose = ctx.obj['verbose']
    service = config['service']

    branch, commit, clean = utils.get_git_info()
    build_tag = utils.get_build_tag(service=service, branch=branch, commit=commit)

    # Repository needs to be clean to build. Otherwise the image can contain
    # uncommited changes.
    if not clean and not force:
        click.secho("Repository is not clean. Clean up or use `--force` "
                    "if you know what you're doing.", fg='yellow')
        ctx.abort()

    click.secho("Building image '{build_tag}'".format(build_tag=build_tag), fg='cyan')
    click.confirm('Do you want to continue?', abort=True)

    # Build and tag local image
    cmd = "docker build --tag {build_tag} source {quiet}".format(
        build_tag=build_tag, quiet='--quiet=true' if not verbose else '')
    utils.run_local(cmd, verbose=True)

    click.echo('Done!')


@ueli.command()
@click.pass_context
def push(ctx):
    """
    Push image to remote registry.
    """
    config = ctx.obj['config']
    service = config['service']

    branch, commit, clean = utils.get_git_info()
    build_tag = utils.get_build_tag(service=service, branch=branch, commit=commit)
    remote = '{gcloud_registry}/{gcloud_project}'.format(
        gcloud_registry=config['gcloud']['registry'],
        gcloud_project=config['gcloud']['project'])

    click.secho("Pushing '{build_tag}' to '{remote}'".format(
        build_tag=build_tag, remote=remote), fg='cyan')
    click.confirm('Do you want to continue?', abort=True)

    # Add remote tag to local image
    remote_tag = '{remote}/{build_tag}'.format(remote=remote, build_tag=build_tag)
    cmd = 'docker tag {build_tag} {remote_tag}'.format(build_tag=build_tag, remote_tag=remote_tag)
    utils.run_local(cmd, verbose=True)

    # Push image to remote server
    cmd = 'gcloud docker -- push {remote_tag}'.format(remote_tag=remote_tag)
    utils.run_local(cmd, verbose=True)

    click.echo('Done!')


@ueli.command()
@click.confirmation_option(prompt='Are you sure you want to delete all docker images?')
def delete_images():
    """
    Delete all local docker images.
    """
    utils.run_local('docker rmi -f $(docker images -q)', verbose=True)


@ueli.command()
@click.pass_context
def set_credentials(ctx):
    """
    Setting the right gcloud cluster credentials for kubectl.
    """
    config = ctx.obj['config']
    gcloud_project = config['gcloud']['project']
    gcloud_cluster = config['gcloud']['cluster']
    cmd = ('gcloud container clusters get-credentials {gcloud_cluster} '
           '--project={gcloud_project}').format(gcloud_cluster=gcloud_cluster,
                                                gcloud_project=gcloud_project)
    utils.run_local(cmd)


def list_type(type, namespace=None):
    namespace_option = '--namespace={}'.format(namespace) if namespace else ''
    cmd = 'kubectl get {type} -o name {namespace_option}'.format(
        type=type, namespace_option=namespace_option)
    return utils.run_local(cmd).split('\n')


def type_exists(type, name, namespace=None):
    names = list_type(type=type, namespace=namespace)
    return '{type}/{name}'.format(type=type, name=name) in names


@ueli.command()
@click.pass_context
def list_environments(ctx):
    ctx.invoke(set_credentials)

    envs = list_type(type='namespace')
    filters = ['namespace/default', 'namespace/kube-system']
    filtered = [env.replace('namespace/', '') for env in envs if not any(f == env for f in filters)]
    click.secho("{} available environments".format(len(filtered)), fg='cyan')
    click.secho("\n".join(filtered), fg='green')


@ueli.command()
@click.argument('environment')
@click.option('--dry-run', is_flag=True, help="Don't create anything")
@click.pass_context
def apply(ctx, environment, dry_run):
    """
    Create a new environment.
    """
    clean, config_keys, secret_keys = ctx.invoke(inspect_deployments)
    if not clean:
        ctx.abort()

    config = ctx.obj['config']
    service = config['service']
    ctx.invoke(set_credentials)

    # Create namespace if not exists
    if not type_exists(type='namespace', name=environment):
        utils.run_local('kubectl create namespace {}'.format(environment),
                        verbose=True, execute=not dry_run)

    # Create configmap if not exists
    config_name = utils.get_config_name(service=service)
    if not type_exists(type='configmap', name=config_name, namespace=environment):
        cmd = 'kubectl create configmap {name} --namespace={environment}'.format(
            name=config_name, environment=environment)
        utils.run_local(cmd, verbose=True, execute=not dry_run)

    # Apply k8s files
    deployments = config['deployments']
    for deployment in deployments:
        for to_apply in deployment['apply']:
            cmd = 'kubectl apply -f {to_apply} --namespace={environment}'.format(
                environment=environment, to_apply=to_apply)
            utils.run_local(cmd, verbose=True, execute=not dry_run)

    if len(config_keys) > 0:
        click.secho("Don't forget to update config with "
                    "`ueli config {environment}`: \n\n{keys}\n".format(
                        environment=environment, keys='\n'.join(config_keys)),
                    fg='cyan')

    if len(secret_keys) > 0:
        click.secho("Don't forget to update secrets: \n\n{keys}\n".format(
            keys='\n'.join(secret_keys)), fg='cyan')

    click.echo('Done!')


@ueli.command()
@click.argument('environment')
@click.pass_context
def config(ctx, environment):
    """
    Opens config map edit from kubectl
    """
    config = ctx.obj['config']
    service = config['service']
    ctx.invoke(set_credentials)

    config_name = utils.get_config_name(service=service)
    cmd = 'kubectl edit configmap {name} --namespace={environment}'.format(
        name=config_name, environment=environment)
    utils.run_local(cmd, output=False, verbose=True)


@ueli.command()
@click.argument('branch')
@click.pass_context
def latest(ctx, branch):
    config = ctx.obj['config']
    repo = config['repository']
    cmd = 'git ls-remote {repo} {branch}'.format(repo=repo, branch=branch)
    commit = utils.run_local(cmd, verbose=True)
    if commit:
        short = commit[:7]
        click.secho("Latest commit on '{branch}' available for deploy is '{commit}'".format(
            branch=branch, commit=short))
        return short
    return None


@ueli.command()
@click.argument('environment')
@click.argument('branch', default='master')
@click.pass_context
def deploy(ctx, environment, branch):
    """
    Deploy specific image tag.
    """
    ctx.invoke(set_credentials)

    if not type_exists(type='namespace', name=environment):
        click.secho("Can not deploy to '{environment}', environment doesn't "
                    "exist. Use `ueli list_environments` to see which one "
                    "exists or `ueli apply NAME` to create "
                    "one.".format(environment=environment), fg='yellow')
        ctx.abort()

    config = ctx.obj['config']
    service = config['service']

    # Special handling for production
    if environment == 'production' and branch != 'master':
        click.secho("Only 'master' can be deployed to 'production'.", fg='yellow')
        ctx.abort()

    commit = ctx.invoke(latest, branch=branch)
    if not commit:
        click.secho("No commit for '{branch}' found on remote repository. `git push`?".format(
            branch=branch), fg='yellow')
        ctx.abort()

    build_tag = utils.get_build_tag(service=service, branch=branch, commit=commit)
    click.secho("Deploying '{build_tag}' to '{environment}'".format(
        build_tag=build_tag, environment=environment), fg='cyan')
    click.confirm('Do you want to continue?', abort=True)

    # remote = '{registry}/{project}'.format(registry=config['gcloud']['registry'],
    #                                        project=config['gcloud']['project'])

    # remote_tag = '{remote}/{build_tag}'.format(remote=remote, build_tag=build_tag)

    # deployments = config['deployments']
    # for deployment in deployments:
    #     container_name = project
    #     cmd = ('kubectl --namespace={namespace} set image deployment/{deployment} '
    #            '{container_name}={remote_tag}'.format(
    #                namespace=namespace,
    #                deployment=deployment,
    #                container_name=container_name,
    #                remote_tag=remote_tag))
    #     click.secho(cmd)
    #     utils.run_local(cmd)


# @click.group()
# @click.option('--branch', prompt='Branch to create a stage environment for',
#               default=lambda: utils.get_git_info()[0])
# @click.pass_context
# def stage(ctx, branch):
#     """
#     Execute commands on stage cluster using branch as namespace.
#     """
#     ctx.obj['environment'] = 'stage'
#     ctx.obj['namespace'] = branch


# ueli.add_command(stage)


# @click.group()
# @click.pass_context
# def production(ctx):
#     """
#     Execute commands on production cluster in production namespace.
#     """
#     ctx.obj['environment'] = 'production'
#     ctx.obj['namespace'] = 'production'

#     # checks
#     branch, commit, clean = utils.get_git_info()
#     if not utils.commit_is_pushed(commit=commit):
#         click.secho("No config file '{}' found".format(CONFIG_FILE_NAME), fg='red')
#         ctx.abort()


# ueli.add_command(production)


# @click.command()
# @click.pass_context
# def config(ctx):
#     """
#     Edit
#     """
#     project = ctx.obj['config']['project']
#     namespace = ctx.obj['namespace']
#     config_name = '{project}-config'.format(project=project)
#     cmd = 'kubectl get configmaps -o name --namespace={}'.format(namespace)
#     configmaps = utils.run_local(cmd).split('\n')
#     exists = 'configmap/{}'.format(config_name) in configmaps

#     with tempfile.NamedTemporaryFile() as fp:
#         # if config already exists, load data into tmp file
#         if exists:
#             cmd = ('kubectl get configmap {config_name} -o json '
#                    '--namespace={namespace}').format(config_name=config_name,
#                                                      namespace=namespace)
#             raw = utils.run_local(cmd)
#             data = json.loads(raw)['data']['config']
#             fp.write(data.encode('utf8'))
#             fp.flush()

#         # lunch users editor of choice
#         click.edit(filename=fp.name)

#         # Create/update config
#         create_cmd = ('kubectl create configmap {config_name} '
#                       '--from-file=config={filename} '
#                       '--namespace={namespace}').format(config_name=config_name,
#                                                         filename=fp.name,
#                                                         namespace=namespace)
#         update_cmd = '{create_cmd} -o yaml --dry-run | kubectl replace -f -'.format(
#             create_cmd=create_cmd)
#         utils.run_local(update_cmd if exists else create_cmd)


# stage.add_command(config)
# production.add_command(config)


# @click.command()
# @click.pass_context
# def apply_services(ctx):
#     """
#     Apply k8s services.
#     """
#     ctx.invoke(set_credentials)
#     config = ctx.obj['config']
#     namespace = ctx.obj['namespace']
#     for service in config['services']:
#         cmd = ('kubectl --namespace={namespace} apply -f '
#                'kubernetes/{service}/{service}-service.yaml'.format(
#                    namespace=namespace,
#                    service=service))
#         click.secho(cmd)
#         utils.run_local(cmd)


# stage.add_command(apply_services)
# production.add_command(apply_services)


# @click.command()
# @click.pass_context
# def apply_deployments(ctx):
#     """
#     Apply k8s deployments.
#     """
#     ctx.invoke(set_credentials)
#     config = ctx.obj['config']
#     namespace = ctx.obj['namespace']
#     for deployment in config['deployments']:
#         cmd = ('kubectl --namespace={namespace} apply -f '
#                'kubernetes/{deployment}/{deployment}-deployment.yaml'.format(
#                    namespace=namespace,
#                    deployment=deployment))
#         click.secho(cmd)
#         utils.run_local(cmd)


# stage.add_command(apply_deployments)
# production.add_command(apply_deployments)


@ueli.command()
@click.pass_context
def inspect_deployments(ctx):
    """
    Goes through all k8s files and checks for naming and collects config keys.

    TODO (silvan): clean up this messy shitty code... you can better
    """
    config = ctx.obj['config']
    service = config['service']
    deployments = config['deployments']

    warnings = set()

    config_name = utils.get_config_name(service=service)
    config_keys = set()

    secret_name = utils.get_secret_name(service=service)
    secret_keys = set()

    for deployment in deployments:

        if not deployment['name'].startswith(service):
            warnings.add("Ueli config deployment name '{name}' doesn't start "
                         "with {service}".format(name=deployment['name'],
                                                 service=service))

        for to_apply in deployment['apply']:
            data = utils.load_yaml_file(path=to_apply)
            if data:
                names = []
                names.append(data['metadata']['name'])
                if 'template' in data['spec'].keys():
                    names.append(data['spec']['template']['metadata']['labels']['name'])

                    # get configs and secrets used as volumes
                    if 'volumes' in data['spec']['template']['spec'].keys():
                        for volume in data['spec']['template']['spec']['volumes']:
                            if 'configMap' in volume.keys():
                                config_keys.add(volume['configMap']['name'])
                            if 'secret' in volume.keys():
                                secret_keys.add(volume['secret']['secretName'])

                    # get configs and secrets used in container ENVS
                    if 'containers' in data['spec']['template']['spec'].keys():
                        for container in data['spec']['template']['spec']['containers']:
                            if 'env' in container.keys():
                                for e in container['env']:
                                    if 'valueFrom' in e.keys():
                                        if 'configMapKeyRef' in e['valueFrom'].keys():
                                            if e['valueFrom']['configMapKeyRef']['name'] == config_name:
                                                config_keys.add(e['valueFrom']['configMapKeyRef']['key'])
                                        if 'secretKeyRef' in e['valueFrom'].keys():
                                            if e['valueFrom']['secretKeyRef']['name'] == secret_name:
                                                secret_keys.add(e['valueFrom']['secretKeyRef']['key'])

                # check correct name naming
                for name in names:
                    if not name.startswith(service):
                        warnings.add("{to_apply}: Name '{name}' doesn't start "
                                     "with {service}".format(to_apply=to_apply,
                                                             name=name,
                                                             service=service))

    click.secho("{} wrong namings".format(len(warnings)), fg='cyan')
    click.secho("{msg}".format(msg='\n'.join(warnings)), fg='yellow')

    click.secho("{} config keys".format(len(config_keys)), fg='cyan')
    click.secho("{keys}".format(keys='\n'.join(config_keys)), fg='green')

    click.secho("{} secret keys".format(len(secret_keys)), fg='cyan')
    click.secho("{keys}".format(keys='\n'.join(secret_keys)), fg='green')

    clean = len(warnings) <= 0
    return clean, config_keys, secret_keys


def main():
    ueli(obj={})
