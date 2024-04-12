# flake8: noqa: F811

from distutils.util import strtobool

from behave import given, then, when

import scripts.parse_ncbi_datasets as parse_ncbi_datasets


@given("a sequence record has location {location}")
def step_impl(context, location):
    context.sequence_record = [{"assigned_molecule_location_type": location}]


@when("we set the organelle name")
def step_impl(context):
    context.organelle_name = parse_ncbi_datasets.set_organelle_name(
        context.sequence_record
    )


@then("the name will be {name}")
def step_impl(context, name):
    assert context.organelle_name == name


@given("a sequence record has no location")
def step_impl(context):
    context.sequence_record = [{}]


@when("we try to set the organelle name")
def step_impl(context):
    context.organelle_name = parse_ncbi_datasets.set_organelle_name(
        context.sequence_record
    )


@then("the name will not be set")
def step_impl(context):
    assert context.organelle_name is None


@given("a sequence record has role {role}")
def step_impl(context, role):
    context.sequence_record = [{"role": role}]


@when("we check if it is chromosomal")
def step_impl(context):
    context.is_assembled = parse_ncbi_datasets.is_assembled_molecule(
        context.sequence_record
    )


@then("the result will be {value}")
def step_impl(context, value):
    assert str(context.is_assembled) == value
