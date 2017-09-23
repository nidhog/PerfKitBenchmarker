# Copyright 2017 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import logging
import time
from perfkitbenchmarker import flags
from perfkitbenchmarker import providers
from perfkitbenchmarker import managed_relational_db
from perfkitbenchmarker import vm_util

from perfkitbenchmarker.providers import azure
from perfkitbenchmarker.providers.azure import azure_network

FLAGS = flags.FLAGS

DEFAULT_POSTGRES_VERSION = '9.6'
DEFAULT_POSTGRES_PORT = 5432

class AzureManagedRelationalDb(managed_relational_db.BaseManagedRelationalDb):
  """An object representing an Azure managed relational database.

  Attributes:
    created: True if the resource has been created.
    pkb_managed: Whether the resource is managed (created and deleted) by PKB.
  """

  CLOUD = providers.AZURE
  SERVICE_NAME = 'managed_relational_db'

  def __init__(self, managed_relational_db_spec):
    super(AzureManagedRelationalDb, self).__init__(managed_relational_db_spec)
    self.spec = managed_relational_db_spec
    self.instance_id = 'pkb-db-instance-' + FLAGS.run_uri
    self.zone = self.spec.vm_spec.zone
    self.resource_group = azure_network.GetResourceGroup()
    #self.compute_units = _ConvertCpusToComputeUnit(self.spec.vm_spec.cpus)
    # TODO: need to find a way to specify compute units and performance tier
    # in the spec
    self.compute_units = 400
    self.performance_tier = "Standard"

  def _ConvertCpusToComputeUnits(cpus):
    """100 compute units equate to a single CPU without hyperthreading"""
    return cpus * 100

  @staticmethod
  def GetDefaultDatabaseVersion(database):
    """Returns the default version of a given database.

    Args:
      database (string): type of database (my_sql or postgres).
    Returns:
      (string): Default database version.
    """
    if database == managed_relational_db.POSTGRES:
      return DEFAULT_POSTGRES_VERSION
    raise Exception('PKB only supports Postgres databases on Azure')

  def GetEndpoint(self):
    return self.endpoint

  def GetPort(self):
    # Azure has no ability to provide a non-default port for Postgres
    if database == managed_relational_db.POSTGRES:
      return DEFAULT_POSTGRES_PORT
    raise Exception('PKB only supports Postgres databases on Azure')

  def _Create(self):
    """Creates the Azure database instance"""
    cmd = [
        azure.AZURE_PATH,
        'postgres',
        'server',
        'create',
        '--name', self.instance_id,
        '--location', self.zone,
        '--admin-user', self.spec.database_username,
        '--admin-password', self.spec.database_password,
        '--storage-size', str(self.spec.disk_spec.disk_size * 1024),
        '--performance-tier', self.performance_tier,
        '--compute-units', str(self.compute_units),
        '--version', self.spec.database_version,
    ] + self.resource_group.args
    vm_util.IssueCommand(cmd)

  def _Delete(self):
    """Deletes the underlying resource.

    Implementations of this method should be idempotent since it may
    be called multiple times, even if the resource has already been
    deleted.
    """
    cmd = [
        azure.AZURE_PATH,
        'postgres',
        'server',
        'delete',
        '-y',
        '--name', self.instance_id,
    ] + self.resource_group.args
    vm_util.IssueCommand(cmd)

  def _RunServerShowCommand(self):
    cmd = [
        azure.AZURE_PATH,
        'postgres',
        'server',
        'show',
        '--name', self.instance_id,
    ] + self.resource_group.args
    return vm_util.IssueCommand(cmd, suppress_warning=True)

  def _Exists(self):
    """Returns true if the underlying resource exists.

    Supplying this method is optional. If it is not implemented then the
    default is to assume success when _Create and _Delete do not raise
    exceptions.
    """
    _, _, retcode = self._RunServerShowCommand()
    return retcode == 0

  def _ParseEndpoint(self, server_show_json):
    return server_show_json['fullyQualifiedDomainName']

  def _IsReady(self):
    """Return true if the underlying resource is ready.

    Supplying this method is optional.  Use it when a resource can exist
    without being ready.  If the subclass does not implement
    it then it just returns true.

    Returns:
      True if the resource was ready in time, False if the wait timed out.
    """
    timeout = 60 * 60 * 6 # 6 hours.
    start_time = datetime.datetime.now()

    while True:
      if (datetime.datetime.now() - start_time).seconds > timeout:
        logging.exception('Timeout waiting for sql instance to be ready')
        return False
      time.sleep(5)
      stdout, _, _ = self._RunServerShowCommand()

      try:
        json_output = json.loads(stdout)
        state = json_output['userVisibleState']
        logging.info('Instance state: {0}'.format(state))
        if state == 'Ready':
          break
      except:
        logging.exception('Error attempting to read stdout. Creation failure.')
        return False
    self.endpoint = self._ParseEndpoint(json_output)
    return True

  def _PostCreate(self):
    """Method that will be called once after _CreateReource is called.

    Supplying this method is optional. If it is supplied, it will be called
    once, after the resource is confirmed to exist. It is intended to allow
    data about the resource to be collected or for the resource to be tagged.
    """
    pass

  def _CreateDependencies(self):
    """Method that will be called once before _CreateResource() is called.

    Supplying this method is optional. It is intended to allow additional
    flexibility in creating resource dependencies separately from _Create().
    """
    pass

  def _DeleteDependencies(self):
    """Method that will be called once after _DeleteResource() is called.

    Supplying this method is optional. It is intended to allow additional
    flexibility in deleting resource dependencies separately from _Delete().
    """
    pass
