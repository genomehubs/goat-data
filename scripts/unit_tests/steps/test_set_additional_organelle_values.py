from unittest import mock

from behave import given, then, when

import scripts.parse_ncbi_datasets as parse_ncbi_datasets


@given("a sequence data {seq}")
def step_given_sequence_data(context, seq):
    context.seq = eval(seq)


@given("an organelle dictionary {organelle}")
def step_given_organelle_dict(context, organelle):
    context.organelle = eval(organelle)


@given("a data dictionary {data}")
def step_given_data_dict(context, data):
    context.data = eval(data)


@given("the name of the organelle {organelle_name}")
def step_given_organelle_name(context, organelle_name):
    context.organelle_name = organelle_name


@given("the assembled molecule flag is {is_assembled}")
def step_given_assembled_flag(context, is_assembled):
    context.is_assembled = eval(is_assembled)


@when("set_additional_organelle_values is called")
def step_when_set_additional_organelle_values_called(context):
    with mock.patch(
        "scripts.parse_ncbi_datasets.is_assembled_molecule"
    ) as mock_is_assembled:
        mock_is_assembled.return_value = context.is_assembled
        parse_ncbi_datasets.set_additional_organelle_values(
            context.seq, context.organelle, context.data, context.organelle_name
        )


@when("initialise_organelle_info is called")
def step_when_initialise_organelle_info_called(context):
    parse_ncbi_datasets.initialise_organelle_info(context.data, context.organelle_name)


@then("the data dictionary should be updated to {expected}")
def step_then_data_updated(context, expected):
    assert context.data == eval(expected)
