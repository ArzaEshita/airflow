# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Scheduler command"""
import signal
from multiprocessing import Process
from typing import Optional

import daemon
from daemon.pidfile import TimeoutPIDLockFile

from airflow import settings
from airflow.jobs.scheduler_job import SchedulerJob
from airflow.utils import cli as cli_utils
from airflow.utils.cli import (
    get_config_with_source,
    process_subdir,
    setup_locations,
    setup_logging,
    sigconf_handler,
    sigint_handler,
    sigquit_handler,
)


def _create_scheduler_job(args):
    job = SchedulerJob(
        subdir=process_subdir(args.subdir),
        num_runs=args.num_runs,
        do_pickle=args.do_pickle,
    )
    return job


def _run_scheduler_job(args):
    skip_serve_logs = args.skip_serve_logs
    job = _create_scheduler_job(args)
    sub_proc = _serve_logs(skip_serve_logs)
    try:
        job.run()
    finally:
        if sub_proc:
            sub_proc.terminate()


@cli_utils.action_cli
def scheduler(args):
    """Starts Airflow Scheduler"""
    print(settings.HEADER)
    print(get_config_with_source())

    if args.daemon:
        pid, stdout, stderr, log_file = setup_locations(
            "scheduler", args.pid, args.stdout, args.stderr, args.log_file
        )
        handle = setup_logging(log_file)
        with open(stdout, 'w+') as stdout_handle, open(stderr, 'w+') as stderr_handle:
            ctx = daemon.DaemonContext(
                pidfile=TimeoutPIDLockFile(pid, -1),
                files_preserve=[handle],
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            with ctx:
                _run_scheduler_job(args=args)
    else:
        signal.signal(signal.SIGINT, sigint_handler)
        signal.signal(signal.SIGTERM, sigint_handler)
        signal.signal(signal.SIGQUIT, sigquit_handler)
        signal.signal(signal.SIGUSR1, sigconf_handler)
        _run_scheduler_job(args=args)


def _serve_logs(skip_serve_logs: bool = False) -> Optional[Process]:
    """Starts serve_logs sub-process"""
    from airflow.configuration import conf
    from airflow.utils.serve_logs import serve_logs

    if conf.get("core", "executor") in ["LocalExecutor", "SequentialExecutor"]:
        if skip_serve_logs is False:
            sub_proc = Process(target=serve_logs)
            sub_proc.start()
            return sub_proc
    return None
