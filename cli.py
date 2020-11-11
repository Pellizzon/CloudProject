#!/usr/bin/env python3

import click
import requests
import json
import datetime

BASE_URL = "http://pellizzonLb-1944810896.us-east-1.elb.amazonaws.com:8080/tasks"


@click.group()
def pellizzon():
    """A CLI wrapper for Cloud Project.

    run chmod 755 cli.py && ./cli.py --help

    or

    python3 cli.py --help

    """


@pellizzon.command()
def tasks():
    """List all tasks."""
    response = requests.get(url=f"{BASE_URL}/list")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print(f"Could not get the tasks: {response.text}")


@click.option(
    "-i",
    "--id_task",
    help="Title of the task",
)
@pellizzon.command()
def get(id_task: str):
    """Get task specified by id."""
    response = requests.get(url=f"{BASE_URL}/{id_task}")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print(f"Could not get task: {response.text}")


@click.option(
    "-t",
    "--title",
    help="Title of the task",
)
@click.option("-d", "--description", help="Task description")
@pellizzon.command()
def create(title: str, description: str):
    """Create new task."""
    pub_date = str(datetime.datetime.now())
    params = {"title": title, "pub_date": pub_date, "description": description}
    response = requests.post(url=f"{BASE_URL}/create", data=json.dumps(params))
    if response.status_code == 201:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print(f"Could not create task: {response.text}")


@click.option(
    "-i",
    "--id_task",
    help="ID of the task to be updated",
)
@click.option(
    "-t",
    "--new_title",
    help="New title of the task",
)
@click.option("-d", "--new_description", help="Task description")
@pellizzon.command()
def update(id_task: str, new_title: str, new_description: str):
    """update task of given id."""
    new_pub_date = str(datetime.datetime.now())
    params = {}
    if new_title:
        params["title"] = new_title
    if new_description:
        params["description"] = new_description
    params["pub_date"] = new_pub_date
    response = requests.put(url=f"{BASE_URL}/update/{id_task}", data=json.dumps(params))
    if response.status_code == 201:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print(f"Could not update task: {response.text}")


@click.option(
    "-i",
    "--id_task",
    help="ID of the task to be deleted",
)
@click.option("-a", "--delete_all", is_flag=True, help="Delete all tasks.")
@pellizzon.command()
def delete(id_task: str, delete_all: bool):
    """delete task of given id or delete all tasks"""
    if id_task:
        response = requests.delete(url=f"{BASE_URL}/delete/{id_task}")
        if response == 200:
            print(response.json())
        else:
            print(response.text)

    if delete_all:
        response = requests.delete(url=f"{BASE_URL}/deleteAll")
        print(response.text)


if __name__ == "__main__":
    pellizzon(prog_name="pellizzon")
