import gettext
import os
import urllib
import sys

from reddwarf.common import cfg
from reddwarf.openstack.common import log as logging
from reddwarf.tests.config import CONFIG
from wsgi_intercept.httplib2_intercept import install as wsgi_install
import proboscis
from eventlet import greenthread
import wsgi_intercept

CONF = cfg.CONF


def add_support_for_localization():
    """Adds support for localization in the logging.

    If ../nova/__init__.py exists, add ../ to Python search path, so that
    it will override what happens to be installed in
    /usr/(local/)lib/python...

    """
    path = os.path.join(os.path.abspath(sys.argv[0]), os.pardir, os.pardir)
    possible_topdir = os.path.normpath(path)
    if os.path.exists(os.path.join(possible_topdir, 'nova', '__init__.py')):
        sys.path.insert(0, possible_topdir)

    gettext.install('nova', unicode=1)


def initialize_reddwarf(config_file):
    from reddwarf.openstack.common import pastedeploy

    cfg.CONF(args=[],
             project='reddwarf',
             default_config_files=[config_file])
    CONF.use_stderr = False
    CONF.log_file = 'rdtest.log'
    logging.setup(None)
    CONF.bind_port = 8779
    CONF.fake_mode_events = 'simulated'
    return pastedeploy.paste_deploy_app(config_file, 'reddwarf', {})


def initialize_database():
    from reddwarf.db import get_db_api
    from reddwarf.instance import models
    from reddwarf.db.sqlalchemy import session
    db_api = get_db_api()
    db_api.drop_db(CONF)  # Destroys the database, if it exists.
    db_api.db_sync(CONF)
    session.configure_db(CONF)
    # Adds the image for mysql (needed to make most calls work).
    models.ServiceImage.create(service_name="mysql", image_id="fake")
    db_api.configure_db(CONF)


def initialize_fakes(app):
    # Set up WSGI interceptor. This sets up a fake host that responds each
    # time httplib tries to communicate to localhost, port 8779.
    def wsgi_interceptor(*args, **kwargs):

        def call_back(env, start_response):
            path_info = env.get('PATH_INFO')
            if path_info:
                env['PATH_INFO'] = urllib.unquote(path_info)
            #print("%s %s" % (args, kwargs))
            return app.__call__(env, start_response)

        return call_back

    wsgi_intercept.add_wsgi_intercept('localhost',
                                      CONF.bind_port,
                                      wsgi_interceptor)

    # Finally, engage in some truly evil monkey business. We want
    # to change anything which spawns threads with eventlet to instead simply
    # put those functions on a queue in memory. Then, we swap out any functions
    # which might try to take a nap to instead call functions that go through
    # this queue and call the functions that would normally run in seperate
    # threads.
    import eventlet
    from reddwarf.tests.fakes.common import event_simulator_sleep
    eventlet.sleep = event_simulator_sleep
    greenthread.sleep = event_simulator_sleep
    import time
    time.sleep = event_simulator_sleep


def replace_poll_until():
    from reddwarf.common import utils as rd_utils
    from reddwarf.tests import util as test_utils
    rd_utils.poll_until = test_utils.poll_until

if __name__=="__main__":
    wsgi_install()
    add_support_for_localization()
    replace_poll_until()
    # Load Reddwarf app
    # Paste file needs absolute path
    config_file = os.path.realpath('etc/reddwarf/reddwarf.conf.test')
    # 'etc/reddwarf/test-api-paste.ini'
    app = initialize_reddwarf(config_file)
    # Initialize sqlite database.
    initialize_database()
    # Swap out WSGI, httplib, and several sleep functions with test doubles.
    initialize_fakes(app)
    # Initialize the test configuration.
    CONFIG.load_from_file('etc/tests/localhost.test.conf')

    from reddwarf.tests.api import flavors
    from reddwarf.tests.api import versions
    from reddwarf.tests.api import instances
    from reddwarf.tests.api import instances_actions
    from reddwarf.tests.api import instances_delete
    from reddwarf.tests.api import instances_mysql_down
    from reddwarf.tests.api import databases
    from reddwarf.tests.api import root
    from reddwarf.tests.api import users
    from reddwarf.tests.api.mgmt import accounts
    from reddwarf.tests.api.mgmt import admin_required
    from reddwarf.tests.api.mgmt import instances
    from reddwarf.tests.api.mgmt import storage
    from reddwarf.tests.guestagent import test_dbaas
    from reddwarf.tests.guestagent import test_manager
    from reddwarf.tests.guestagent import test_service
    from reddwarf.tests.guestagent import test_query

    proboscis.TestProgram().run_and_exit()
