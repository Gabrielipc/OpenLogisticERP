"""QAbstractTableModel adapter for report preview tables."""

from __future__ import annotations

from typing import Any

from openlogistic_erp.domain.reports import ReportTable
from openlogistic_erp.infrastructure.reports.export.formatting import format_cell

from ..qt import QApplication, Property, QAbstractTableModel, QmlNamedElement, QmlUncreatable, QModelIndex, Qt, Signal, Slot

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("ReportTableModel")
@QmlUncreatable("ReportTableModel instances are created in Python and injected into QML.")
class ReportTableModel(QAbstractTableModel):
    _ROW_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
    _COLUMN_KEY_ROLE = Qt.ItemDataRole.UserRole + 2
    sortChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._table: ReportTable | None = None
        self._rows: list[dict[str, Any]] = []
        self._columns: list[dict[str, Any]] = []
        self._sort_field = ""
        self._sort_direction = ""

    @Property(str, notify=sortChanged)
    def sort_field(self) -> str:
        return self._sort_field

    @Property(str, notify=sortChanged)
    def sort_direction(self) -> str:
        return self._sort_direction

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if (
            not index.isValid()
            or index.row() < 0
            or index.row() >= len(self._rows)
            or index.column() < 0
            or index.column() >= len(self._columns)
        ):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self.display_data(index.row(), index.column())
        if role == self._ROW_DATA_ROLE:
            return self.row_data(index.row())
        if role == self._COLUMN_KEY_ROLE:
            return str(self._columns[index.column()].get("key", ""))
        return None

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return str(self._columns[section].get("label", ""))
            return None
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            int(Qt.ItemDataRole.DisplayRole): b"display",
            self._ROW_DATA_ROLE: b"rowData",
            self._COLUMN_KEY_ROLE: b"columnKey",
        }

    def set_report_table(self, table: ReportTable | None, currency_key: str = "") -> None:
        self.beginResetModel()
        try:
            self._table = table
            self._sort_field = ""
            self._sort_direction = ""
            if table is None:
                self._rows = []
                self._columns = []
                return
            self._rows = [dict(row) for row in self._rows_for_currency(table, currency_key)]
            self._columns = [column.to_map() for column in table.columns]
        finally:
            self.endResetModel()
        self.sortChanged.emit()

    @staticmethod
    def _rows_for_currency(table: ReportTable, currency_key: str) -> tuple[dict[str, Any], ...]:
        normalized = str(currency_key or "").strip()
        if not normalized or not table.currency_field:
            return tuple(dict(row) for row in table.rows)
        return tuple(dict(row) for row in table.rows if str(row.get(table.currency_field, "")) == normalized)

    @Slot(int, int, result=str)
    def display_data(self, row: int, column: int) -> str:
        if self._table is None:
            return ""
        if row < 0 or row >= len(self._rows):
            return ""
        if column < 0 or column >= len(self._table.columns):
            return ""

        report_column = self._table.columns[column]
        row_data = self._rows[row]
        currency = row_data.get(self._table.currency_field or "moneda") if report_column.format == "currency" else None
        return format_cell(report_column, row_data.get(report_column.key), currency=currency)

    @Slot(int, int, int, int, result=str)
    def display_range_as_tsv(
        self,
        start_row: int,
        start_column: int,
        end_row: int,
        end_column: int,
    ) -> str:
        if not self._rows or not self._columns:
            return ""

        first_row = max(0, min(int(start_row), int(end_row)))
        last_row = min(len(self._rows) - 1, max(int(start_row), int(end_row)))
        first_column = max(0, min(int(start_column), int(end_column)))
        last_column = min(len(self._columns) - 1, max(int(start_column), int(end_column)))
        if first_row > last_row or first_column > last_column:
            return ""

        lines: list[str] = []
        for row_index in range(first_row, last_row + 1):
            values = [
                self._sanitize_tsv_cell(self.display_data(row_index, column_index))
                for column_index in range(first_column, last_column + 1)
            ]
            lines.append("\t".join(values))
        return "\n".join(lines)

    @Slot(int, int, int, int, result=bool)
    def copy_display_range_to_clipboard(
        self,
        start_row: int,
        start_column: int,
        end_row: int,
        end_column: int,
    ) -> bool:
        text = self.display_range_as_tsv(start_row, start_column, end_row, end_column)
        if text == "":
            return False
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        return True

    @Slot(int, result=object)
    def row_data(self, row: int) -> dict[str, Any]:
        if row < 0 or row >= len(self._rows):
            return {}
        return dict(self._rows[row])

    @Slot(int, result=object)
    def column_data(self, column: int) -> dict[str, Any]:
        if column < 0 or column >= len(self._columns):
            return {}
        return dict(self._columns[column])

    @Slot(str)
    def toggle_sort(self, column_key: str) -> None:
        normalized_key = str(column_key or "").strip()
        if not normalized_key or normalized_key not in {str(column.get("key", "")) for column in self._columns}:
            return

        next_direction = "desc" if self._sort_field == normalized_key and self._sort_direction == "asc" else "asc"
        self.beginResetModel()
        try:
            self._sort_field = normalized_key
            self._sort_direction = next_direction
            valued_rows = [row for row in self._rows if row.get(normalized_key) is not None]
            empty_rows = [row for row in self._rows if row.get(normalized_key) is None]
            valued_rows.sort(
                key=lambda row: self._sort_value(row.get(normalized_key)),
                reverse=next_direction == "desc",
            )
            self._rows = [*valued_rows, *empty_rows]
        finally:
            self.endResetModel()
        self.sortChanged.emit()

    @staticmethod
    def _sort_value(value: Any) -> tuple[int, float | str]:
        if isinstance(value, bool):
            return (0, float(value))
        if isinstance(value, (int, float)):
            return (0, float(value))
        if hasattr(value, "isoformat"):
            return (1, str(value.isoformat()).casefold())
        return (2, str(value).casefold())

    @staticmethod
    def _sanitize_tsv_cell(value: str) -> str:
        return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
