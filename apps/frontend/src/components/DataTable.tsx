export function DataTable({
  columns,
  rows,
  maxRows = 12,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
  maxRows?: number;
}) {
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">데이터 미리보기, 최대 {maxRows}행</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, maxRows).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
