from pathlib import Path

from gpc_dtwin.context import ApplicationContext


def test_database_backup_and_restore(tmp_path):
    database = tmp_path / "active.sqlite3"
    context = ApplicationContext(database_path=database)
    context.bootstrap()
    original = len(context.dataframe)
    backup = context.backup_database(tmp_path / "backup.sqlite3", emit=False)
    assert backup.is_file()
    context.repository.update_data_status("GPC-0001", "VERIFIED")
    context.reload(emit=False)
    assert context.dataframe.loc[context.dataframe.record_id == "GPC-0001", "data_status"].iloc[0] == "VERIFIED"
    context.restore_database(backup, emit=False)
    assert len(context.dataframe) == original
    assert context.dataframe.loc[context.dataframe.record_id == "GPC-0001", "data_status"].iloc[0] != "VERIFIED"
