function redirect(path) {
	console.log(path)
	window.location.replace(window.location.origin + path);
};

function activateButton($btn) {
	$btn.removeClass('disabled').prop('disabled', false);
};

function deactivateButton($btn) {
	$btn.addClass('disabled').prop('disabled', true);
};

function closeAllModalDialog() {
	$('.modal[role="dialog"]').modal('hide');
};
