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
"""Test for managed relational database provisioning.

This is a set of benchmarks that measures performance of SQL Databases on
managed MySQL services.

- On AWS, we will use RDS+MySQL and RDS PostgreSQL.
- On GCP, we will use Cloud SQL v2 (Performance Edition).
As other cloud providers deliver a managed SQL service, we will add it here.

To run this benchmark the following flags can be used to overwrite config:
- database: {mysql, postgres} Declares type of database.
- database_name: Defaults to 'pkb-db-{run_uri}'.
- database_username: Defaults to 'pkb-db-user-{run_uri}'.
- database_password: Defaults to random 10-character alpha-numeric string.
- database_version: {5.7, 9.6} Defaulted to latest for type.
- high_availability: Boolean.
- data_disk_size: integer. Storage size.


As of June 2017 to make this benchmark run for GCP you must install the
gcloud beta component. This is necessary because creating a Cloud SQL instance
with a non-default storage size is in beta right now. This can be removed when
this feature is part of the default components.
See https://cloud.google.com/sdk/gcloud/reference/beta/sql/instances/create
for more information.
To run this benchmark for GCP it is required to install a non-default gcloud
component. Otherwise this benchmark will fail.
To ensure that gcloud beta is installed, type
        'gcloud components list'
into the terminal. This will output all components and status of each.
Make sure that
  name: gcloud Beta Commands
  id:  beta
has status: Installed.
If not, run
        'gcloud components install beta'
to install it. This will allow this benchmark to properly create an instance.
"""

from perfkitbenchmarker import configs

BENCHMARK_NAME = 'pgbench'
BENCHMARK_CONFIG = """
pgbench:
  description: test managed relational database provisioning
  managed_relational_db:
    database: postgres
    vm_spec:
      GCP:
        machine_type:
          cpus: 16
          memory: 54GiB
        zone: us-central1-c
      AWS:
        machine_type: db.t1.micro
        zone: us-west-2a
    disk_spec:
      GCP:
        disk_size: 1000
        disk_type: pd-ssd
      AWS:
        disk_size: 5
        disk_type: gp2
  vm_groups:
    default:
      vm_spec:
        GCP:
          machine_type: n1-standard-16
          image: ubuntu-1604-xenial-v20170815a
          image_project: ubuntu-os-cloud
      disk_spec: *default_50_gb
"""


def GetConfig(user_config):
  config = configs.LoadConfig(BENCHMARK_CONFIG, user_config, BENCHMARK_NAME)
  return config


def CheckPrerequisites(benchmark_config):
  """Verifies that the required resources are present.

  Raises:
    perfkitbenchmarker.data.ResourceNotFound: On missing resource.
  """
  pass


def Prepare(benchmark_spec):
  vm = benchmark_spec.vms[0]
  vm.Install('pgbench')

  test_db_name = 'perftest'
  default_db_name = 'postgres'
  db = benchmark_spec.managed_relational_db
  endpoint = db.GetEndpoint()
  username = db.GetUsername()
  password = db.GetPassword()
  connection_string = MakePsqlConnectionString(
      endpoint, username, password, default_db_name)

  CreateDatabase(benchmark_spec, username, password,
                 default_db_name, endpoint, test_db_name)

  scale_factor = 4000
  stdout, _ = vm.RemoteCommand('pgbench -i -s {0} {1} {2}'.format(
      scale_factor, connection_string, db_name))


def MakePsqlConnectionString(endpoint, user, password, database):
  return '\'host={0} user={1} password={2} dbname={3}\''.format(
      endpoint, user, password, database)


def CreateDatabase(benchmark_spec, user, password, default_database,
                   endpoint, new_database):
  connection_string = MakePsqlConnectionString(endpoint, user, password,
                                               default_database)
  command = 'psql {0} -c "CREATE DATABASE {1};"'.format(connection_string,
                                                        new_database)
  stdout, _ = benchmark_spec.vms[0].RemoteCommand(command, should_log=True)


def Run(benchmark_spec):
  test_db_name = 'perftest'
  db = benchmark_spec.managed_relational_db
  endpoint = db.GetEndpoint()
  username = db.GetUsername()
  password = db.GetPassword()
  connection_string = MakePsqlConnectionString(
      endpoint, username, password, test_db_name)


  command = ('pgbench {0} -c 16 -j 16 -T 30 -P 1 '
             '-r {1}'.format(connection_string, test_db_name))
  benchmark_spec.vms[0].RemoteCommand(command, should_log=True)
  return []


def Cleanup(benchmark_spec):
  pass
