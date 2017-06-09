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
	}, {
		name: 'id',
		label: '_HIDDEN',  //->https://github.com/webismymind/editablegrid/issues/153
		editable: false,
		datatype: 'integer'
	}
];


var resourcesGrid = new EditableGrid('Resources');


function activateButton($btn) {
	$btn.removeClass('disabled').prop('disabled', false);
};


function deactivateButton($btn) {
	$btn.addClass('disabled').prop('disabled', true);
};


function closeAllModalDialog() {
	$('.modal[role="dialog"]').modal('hide');
};


var $modal = $('.modal[role="dialog"]')
	.modal({'backdrop': 'static', 'show': false})  // Important!
	.on('show.bs.modal', function(e) {
		closeAllModalDialog();
	})
	.on('hidden.bs.modal', function(e) {
		$(this).find('.modal-body').empty();
		$(this).find('.modal-title').val('');
	});


$('#datasets button[name="delete-dataset"]')
	.on('click', function(e) {
		e.preventDefault();

		var $button = $('<button/>')
			.prop('type', 'button')
			.prop('class', 'btn btn-danger disabled')
			.prop('disabled', true)
			.text('Oui, supprimer définitivement ce jeu de données')
			.on('click', function(e) {
				e.preventDefault();
				closeAllModalDialog();
				$.ajax({
					type: 'DELETE',
					// success: function() {},
					url: DATASET_URL + '?id=' + resourcesGrid.getRowValues(resourcesGrid.lastSelectedRowIndex)['id']
				})
				.done(function(response, textStatus, jqXHR) {
					// $modal.find('.close').remove();
					$modal.find('.modal-title').text('Information');
					$modal.find('.modal-body').append(jqXHR.responseText);
					$modal.modal('show');
				})
				.fail(function(jqXHR, textStatus, errorThrown) {
					// $modal.find('.close').remove();
					$modal.find('.modal-title').text("L'opération a échouée");
					$modal.find('.modal-body').append(jqXHR.responseText);
					$modal.modal('show');
				});
				e.stopPropagation();
			});

		var $input = $('<input/>')
			.prop('type', 'text')
			.prop('class', 'form-control')
			.prop('placeholder', 'Nom du jeu de données à supprimer')
			.on('input', function(e) {
				if ($(this).val() === resourcesGrid.getRowValues(resourcesGrid.lastSelectedRowIndex)['name']) {
					$button.removeClass('disabled').prop('disabled', false);
				} else {
					$button.addClass('disabled').prop('disabled', true);
				};
			});

		$modal.find('.modal-title').text('Êtes-vous absolument sûr ?');
		$modal.find('.modal-body')
			.append('<p>Cette action est irreversible et supprimera <strong>définitivement</strong> le jeu de données ainsi que toutes les ressources qui lui sont attachées.</p>')
			.append(
				$('<form/>')
					.append(
						$('<div/>').prop('class', 'form-group')
							.append('<p>Pour confirmer, veuillez réécrire le nom du jeu de données à supprimer.</p>')
							.append($input))
					.append(
						$('<div class="buttons-on-the-right-side">')
							.append($button)
							.append('<button type="button" class="btn btn-default" data-dismiss="modal">Annuler</button>')));
		$modal.modal('show');
		e.stopPropagation();
	});

$('#datasets button[name="modify-dataset"]')
	.on('click', function(e) {
		e.preventDefault();
		redirect(DATASET_URL + '?id=' + resourcesGrid.getRowValues(resourcesGrid.lastSelectedRowIndex)['id']);
		e.stopPropagation();
	});


resourcesGrid.initializeGrid = function() {
	var grid = resourcesGrid;
	var $buttons = $($('#' + this.currentContainerid).parent().get(0)).find('button');

	with (this) {
		rowSelected = function(pRowIdx, nRowIdx) {
			$(grid.getRow(pRowIdx)).removeClass('selected');
			$buttons.each(function() {
				deactivateButton($(this));
			});
			if (pRowIdx != nRowIdx) {
				$(grid.getRow(nRowIdx)).addClass('selected');
				$buttons.each(function() {
					activateButton($(this));
				});
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
	var $containerId = $('#' + containerId);
	var $parent = $($containerId.parent().get(0));
	$parent.find('div[role="alert"]').remove();
	$parent.find('button').each(function() {
		deactivateButton($(this));
	});
	if (data.length > 0) {
		grid.load({'metadata': metadata, 'data': data});
		grid.renderGrid(containerId, GRID_CLASS_NAME_PROPERTY);
		grid.initializeGrid();
		grid.refreshGrid();
		$containerId.show();
	} else {
		$containerId.hide();
		$containerId.after('<div role="alert" class="alert alert-warning"><p>C\'est vide. Cliquez sur le bouton <strong>[ ' + $parent.find('a[name="add-dataset"]').get(0).text + ' ]</strong> pour commencer.</p><div/>');
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
							data[i][1],
							data[i][2],
							data[i][3],
							data[i][4],
							data[i][5],
							data[i][0]  // =id
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


function redirect(path) {
	window.location.replace(window.location.origin + path);
};

window.onhashchange = function(e) {
	$('#menu a[href="' + window.location.hash + '"]').tab('show');
	e.preventDefault();
};


window.onload = function(e) {
	var hash = window.location.hash;
	$('#menu a[href="' + ((HASH_MENU.indexOf(hash) === -1) ? HASH_MENU[0] : hash) + '"]').tab('show');
	e.preventDefault();
};

function overlay() {
	el = document.getElementById("overlay");
	el.style.visibility = (el.style.visibility == "visible") ? "hidden" : "visible";
}