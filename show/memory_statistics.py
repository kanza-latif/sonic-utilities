import click
from tabulate import tabulate

import utilities_common.cli as clicommon


#
# 'memory-statistics' group (show memory-statistics ...)
#
@click.group(cls=clicommon.AliasedGroup, name="memory-statistics")
def memory_statistics():
    """Show memory statistics configuration and logs"""
    pass


def get_memory_statistics_config(field_name, db_connector):
    """Fetches the configuration of memory_statistics from `CONFIG_DB`.

    Args:
      field_name: A string containing the field name in the sub-table of 'memory_statistics'.

    Returns:
      field_value: If field name was found, then returns the corresponding value.
                   Otherwise, returns "Unknown".
    """
    field_value = "Unknown"
    config_db = db_connector  # Use the injected mock db connector
    memory_statistics_table = config_db.get_table("MEMORY_STATISTICS")
    if (memory_statistics_table and
            "memory_statistics" in memory_statistics_table and
            field_name in memory_statistics_table["memory_statistics"]):
        field_value = memory_statistics_table["memory_statistics"][field_name]

    return field_value


@memory_statistics.command(name="config", short_help="Show the configuration of memory statistics")
@click.pass_context
def config(ctx):
    admin_mode = "Disabled"
    db_connector = ctx.obj["db_connector"]  # Retrieve the db connector from context
    admin_enabled = get_memory_statistics_config("enabled", db_connector)
    if admin_enabled == "true":
        admin_mode = "Enabled"

    click.echo("Memory Statistics administrative mode: {}".format(admin_mode))

    retention_time = get_memory_statistics_config("retention_time", db_connector)
    click.echo("Memory Statistics retention time (days): {}".format(retention_time))

    sampling_interval = get_memory_statistics_config("sampling_interval", db_connector)
    click.echo("Memory Statistics sampling interval (minutes): {}".format(sampling_interval))


def fetch_memory_statistics(starting_time=None, ending_time=None, select=None, db_connector=None):
    """Fetch memory statistics from the database.

    Args:
        starting_time: The starting time for filtering the statistics.
        ending_time: The ending time for filtering the statistics.
        additional_options: Any additional options for filtering or formatting.

    Returns:
        A list of memory statistics entries.
    """
    config_db = db_connector  # Use the injected mock db connector
    memory_statistics_table = config_db.get_table("MEMORY_STATISTICS")
    filtered_statistics = []

    for key, entry in memory_statistics_table.items():
        # Add filtering logic here based on starting_time, ending_time, and select
        if (not starting_time or entry.get("time") >= starting_time) and \
           (not ending_time or entry.get("time") <= ending_time):
            # Implement additional filtering based on select if needed
            filtered_statistics.append(entry)

    return filtered_statistics


@memory_statistics.command(name="logs", short_help="Show memory statistics logs with optional filtering")
@click.argument('starting_time', required=False)
@click.argument('ending_time', required=False)
@click.argument('additional_options', required=False, nargs=-1)
@click.pass_context
def show_memory_statistics_logs(ctx, starting_time, ending_time, select):
    """Show memory statistics logs with optional filtering by time and select."""

    db_connector = ctx.obj["db_connector"]  # Retrieve the db connector from context
    # Fetch memory statistics
    memory_statistics = fetch_memory_statistics(
        starting_time,
        ending_time,
        select,
        db_connector=db_connector
    )

    if not memory_statistics:
        click.echo("No memory statistics available for the given parameters.")
        return

    # Display the memory statistics
    headers = ["Time", "Statistic", "Value"]  # Adjust according to the actual fields
    table_data = [[entry.get("time"), entry.get("statistic"), entry.get("value")] for entry in memory_statistics]

    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
