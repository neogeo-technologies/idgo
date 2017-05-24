/* js/main.js */

var HASH_MENU = [];


var DATE_FORMAT = 'dddd Do MMMM YYYY à HH:mm:ss';


var GRID_CLASS_NAME_PROPERTY = 'table table-striped table-bordered table-hover table-condensed';


var RESOURCES_CONTAINER = 'table-resources';


var RESOURCE_METADATA = [
	{
		name: 'name',
		label: 'Nom',
		editable: false,
		datatype: 'string'
	}, {
		name: 'description',
		label: 'Description',
		editable: false,
		datatype: 'string'
	}, {
		name: 'date_creation',
		label: 'Date de création',
		editable: false,
		datatype: 'string'
	}, {
		name: 'last_modification',
		label: 'Dernière modification',
		editable: false,
		datatype: 'string'
	}, {
		name: 'published',
		label: 'Publié',
		editable: false,
		datatype: 'boolean'
	}
];


function activateButton($btnList) {
	for (var i = 0; i < $btnList.length; i ++) {
		$btnList[i].removeClass('disabled').prop('disabled', false);
	};
};


function deactivateButton($btnList) {
	for (var i = 0; i < $btnList.length; i ++) {
		$btnList[i].addClass('disabled').prop('disabled', true);
	};
};


var $deleteDataset = $('#datasets a[name="delete-dataset"]')
	.on('click', function(e) {
		e.preventDefault();
		alert('TODO');
		e.stopPropagation();
	});


var $modifyDataset = $('#datasets a[name="modify-dataset"]')
	.on('click', function(e) {
		e.preventDefault();
		alert('TODO');
		e.stopPropagation();
	});


var resourcesGrid = new EditableGrid('Resources');


resourcesGrid.initializeGrid = function() {
	var grid = resourcesGrid;
	deactivateButton([$deleteDataset, $modifyDataset]);
	with (this) {
		rowSelected = function(pRowIdx, nRowIdx) {
			$(grid.getRow(pRowIdx)).removeClass('selected');
			deactivateButton([$deleteDataset, $modifyDataset]);
			if (pRowIdx != nRowIdx) {
				$(grid.getRow(nRowIdx)).addClass('selected');
				activateButton([$deleteDataset, $modifyDataset]);
			};
		};
		setCellRenderer('published', new CellRenderer({
			render: function(cell, value) {
				cell.style.textAlign = 'center';
				cell.style.width = '32px';
				cell.innerHTML = (value == true) ? '<span class="glyphicon glyphicon-ok"></span>' : '';
			}
		}));
		setCellRenderer('date_creation', new CellRenderer({
			render: function(cell, value) {
				cell.innerHTML = moment(value).format(DATE_FORMAT);
			}
		}));
		setCellRenderer('last_modification', new CellRenderer({
			render: function(cell, value) {
				cell.innerHTML = moment(value).format(DATE_FORMAT);
			}
		}));
	};
};


function updateGrid(grid, containerId, metadata, data) {
	$containerId = $('#' + containerId);
	$($containerId.parent().get(0)).find('div[role="alert"]').remove();
	if (data.length > 0) {
		grid.load({'metadata': metadata, 'data': data});
		grid.renderGrid(containerId, GRID_CLASS_NAME_PROPERTY);
		grid.initializeGrid();
		grid.refreshGrid();
		$containerId.show();
	} else {
		$containerId.after('<div role="alert" class="alert alert-info"><p>C\'est vide. Cliquez sur le bouton <strong>{Ajouter}</strong> pour commencer.</p><div/>');
		$containerId.hide();
	};
};


function loadTab(hash) {
	if (hash === HASH_MENU[0]) {
		updateGrid(
			resourcesGrid,
			RESOURCES_CONTAINER,
			RESOURCE_METADATA,
			(function(data) {
				var m = [];
				for (var i = 0; i < data.length; i ++) {
					m.push({
						id: i,
						values: [
							data[i][0],
							data[i][1],
							data[i][2],
							data[i][3],
							data[i][4]
						]
					});
				};
				return m;
			})(DATASETS)
		);
	};
};


$('#menu a[data-toggle="tab"]')
	.each(function(e) {
		HASH_MENU.push($(this).prop('hash'));
	})
	.on('hide.bs.tab', function(e) {
		e.stopPropagation();
	})
	.on('show.bs.tab', function(e) {
		e.stopPropagation();
		var $this = $(e.target);
		var $thisHash = $this.prop('hash')
		loadTab($thisHash);
		window.location = $thisHash;
	});


window.onhashchange = function(e) {
	$('#menu a[href="' + window.location.hash + '"]').tab('show');
	e.preventDefault();
};


window.onload = function(e) {
	var hash = window.location.hash;
	$('#menu a[href="' + ((HASH_MENU.indexOf(hash) === -1) ? HASH_MENU[0] : hash) + '"]').tab('show');
	e.preventDefault();
};
