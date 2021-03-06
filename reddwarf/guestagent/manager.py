from reddwarf.guestagent import dbaas
from reddwarf.guestagent import volume
from reddwarf.openstack.common import log as logging
from reddwarf.openstack.common import periodic_task

LOG = logging.getLogger(__name__)

MYSQL_BASE_DIR = "/var/lib/mysql"


class Manager(periodic_task.PeriodicTasks):

    @periodic_task.periodic_task(ticks_between_runs=10)
    def update_status(self, context):
        """Update the status of the MySQL service"""
        dbaas.MySqlAppStatus.get().update()

    def create_database(self, context, databases):
        return dbaas.MySqlAdmin().create_database(databases)

    def create_user(self, context, users):
        dbaas.MySqlAdmin().create_user(users)

    def delete_database(self, context, database):
        return dbaas.MySqlAdmin().delete_database(database)

    def delete_user(self, context, user):
        dbaas.MySqlAdmin().delete_user(user)

    def list_databases(self, context, limit=None, marker=None,
                       include_marker=False):
        return dbaas.MySqlAdmin().list_databases(limit, marker,
                                                 include_marker)

    def list_users(self, context, limit=None, marker=None,
                   include_marker=False):
        return dbaas.MySqlAdmin().list_users(limit, marker,
                                             include_marker)

    def enable_root(self, context):
        return dbaas.MySqlAdmin().enable_root()

    def is_root_enabled(self, context):
        return dbaas.MySqlAdmin().is_root_enabled()

    def prepare(self, context, databases, memory_mb, users, device_path=None,
                mount_point=None):
        """Makes ready DBAAS on a Guest container."""
        dbaas.MySqlAppStatus.get().begin_mysql_install()
        # status end_mysql_install set with install_and_secure()
        app = dbaas.MySqlApp(dbaas.MySqlAppStatus.get())
        restart_mysql = False
        if device_path:
            device = volume.VolumeDevice(device_path)
            device.format()
            if app.is_installed():
                #stop and do not update database
                app.stop_mysql()
                restart_mysql = True
                #rsync exiting data
                device.migrate_data(MYSQL_BASE_DIR)
            #mount the volume
            device.mount(mount_point)
            LOG.debug(_("Mounted the volume."))
            #check mysql was installed and stopped
            if restart_mysql:
                app.start_mysql()
        app.install_and_secure(memory_mb)
        LOG.info("Creating initial databases and users following successful "
                 "prepare.")
        self.create_database(context, databases)
        self.create_user(context, users)
        LOG.info('"prepare" call has finished.')

    def restart(self, context):
        app = dbaas.MySqlApp(dbaas.MySqlAppStatus.get())
        app.restart()

    def start_mysql_with_conf_changes(self, context, updated_memory_size):
        app = dbaas.MySqlApp(dbaas.MySqlAppStatus.get())
        app.start_mysql_with_conf_changes(updated_memory_size)

    def stop_mysql(self, context):
        app = dbaas.MySqlApp(dbaas.MySqlAppStatus.get())
        app.stop_mysql()
