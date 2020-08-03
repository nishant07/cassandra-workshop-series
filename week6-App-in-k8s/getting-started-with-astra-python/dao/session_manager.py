import os
import logging
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import dict_factory
from cassandra import Unauthorized, Unavailable, AuthenticationFailed, OperationTimedOut, ReadTimeout


# Sharing a DataStax Driver Session object throughout the application is a best practice
# Here we use a Singleton pattern to ensure that we will be re-using the same Session instance
# wherever we make calls to the database
class SessionManager(object):

    __instance = None
    username = None
    password = None
    keyspace = None
    secure_connect_bundle_path = None
    initialized = False
    _session = None

    ping_query = "SELECT data_center FROM system.local"

    @staticmethod
    def get_instance():
        if SessionManager.__instance is None:
            SessionManager()
        return SessionManager.__instance

    def __init__(self):
        SessionManager.__instance = self

    # only needed for astra
    def save_credentials(self, username, password, keyspace, secure_connection_bundle_path):
        self.username = username
        self.password = password
        self.keyspace = keyspace
        self.secure_connect_bundle_path = secure_connection_bundle_path
        self.initialized = True

    #only needed for astra
    def test_credentials(self, username, password, keyspace, secure_connection_bundle_path):
        temp_session = None
        success = False
        try:
            # This is how you use the Astra secure connect bundle to connect to an Astra database
            # note that the database username and password required.
            # note that no contact points or any other driver customization is required.
            astra_config = {
                'secure_connect_bundle': secure_connection_bundle_path
            }

            cluster = Cluster(cloud=astra_config, auth_provider=PlainTextAuthProvider(username, password))

            temp_session = cluster.connect(keyspace=keyspace)
            result = temp_session.execute(self.ping_query)
            success = True
        except (Unauthorized, Unavailable, AuthenticationFailed, OperationTimedOut, ReadTimeout) as e:
            raise e
        finally:
            if temp_session is not None:
                temp_session.shutdown()
            return success

    def connect(self):
        if self.initialized is False:
            raise Exception('Please initialize the connection parameters first with SessionManager.save_credentials')

        if self._session is None:
            # This is how you use the Astra secure connect bundle to connect to an Astra database
            # note that the database username and password required.
            # note that no contact points or any other driver customization is required.
            if os.getenv('USE_ASTRA') == true:
                astra_config = {
                    'secure_connect_bundle': self.secure_connect_bundle_path
                }

                cluster = Cluster(cloud=astra_config, auth_provider=PlainTextAuthProvider(self.username, self.password))
                self._session = cluster.connect(keyspace=self.keyspace)
            elif os.getenv('USE_ASTRA') == false:
                cluster = Cluster([os.getenv('CONNECTION_POINTS')],auth_provider=PlainTextAuthProvider(os.getenv('USERNAME'), os.getenv('PASSWORD')))
                self._session = cluster.connect(keyspace=os.getenv('KEYSPACE'))
            else:
                logger.info("Missing env value for USE_ASTRA")


            # have the driver return results as dict
            self._session.row_factory = dict_factory

            # have the driver return LocationUDT as a dict
            cluster.register_user_type(self.keyspace, 'location_udt', dict)

        return self._session

    def check_connection(self):
        try:
            result = self.connect().execute(self.ping_query)
            return True
        except (Unauthorized, Unavailable, AuthenticationFailed, OperationTimedOut, ReadTimeout) as e:
            return False

    def close(self):
        if self.initialized and self._session is not None:
            self._session.shutdown()
