from computer.tools.filesystem import get_user_backend
import csv
import io
from shared_server_libs.agent_db_access.domain.schema.query_result import QueryResult
from deepagents.backends.protocol import WriteResult

def save_file_via_vir_fs(user_id: str, file_path: str, content: str) -> WriteResult:
    backend = get_user_backend(user_id)
    result = backend.write(file_path, content)
    return result



def query_result_to_csv(result: QueryResult) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    if result.columns:
        writer.writerow(result.columns)
    if result.rows:
        writer.writerows(result.rows)
    return output.getvalue()


def save_query_result_to_file(user_id: str, file_path: str, result: QueryResult) -> WriteResult:
    csv_string = query_result_to_csv(result)
    return save_file_via_vir_fs(user_id, file_path, csv_string)