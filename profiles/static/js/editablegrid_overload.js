/* */

EditableGrid.prototype.editCell = function(rowIndex, columnIndex) {
	var target = this.getCell(rowIndex, columnIndex);
	with(this) {
		var column = columns[columnIndex];
		if (column) {
			// if another row has been selected: callback
			if (rowIndex > -1) {
				rowSelected(lastSelectedRowIndex, rowIndex);
				if (lastSelectedRowIndex == rowIndex) {
					lastSelectedRowIndex = -1;
				} else {
					lastSelectedRowIndex = rowIndex;
				};
			};
			// edit current cell value
			if (!column.editable) {
				readonlyWarning(column);
			} else {
				if (rowIndex < 0) {
					if (column.headerEditor && isHeaderEditable(rowIndex, columnIndex))
					column.headerEditor.edit(rowIndex, columnIndex, target, column.label);
				} else if (column.cellEditor && isEditable(rowIndex, columnIndex))
				column.cellEditor.edit(rowIndex, columnIndex, target, getValueAt(rowIndex, columnIndex));
			};
		};
	};
};
