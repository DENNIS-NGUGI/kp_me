// Initialize Select2 globally
(function($) {
    'use strict';
    
    // Function to initialize Select2
    function initSelect2() {
        $('select[multiple], select.select2').each(function() {
            // Skip if already initialized
            if ($(this).data('select2')) {
                return;
            }
            
            const isInModal = $(this).closest('.modal').length > 0;
            
            $(this).select2({
                theme: 'bootstrap-5',
                width: '100%',
                placeholder: 'Select options...',
                allowClear: true,
                closeOnSelect: false,
                dropdownParent: isInModal ? $(this).closest('.modal') : $(document.body)
            });
        });
    }
    
    // Initialize on page load
    $(document).ready(function() {
        initSelect2();
    });
    
    // Re-initialize after modal opens
    $(document).on('shown.bs.modal', function() {
        initSelect2();
    });
    
    // Re-initialize after any AJAX content load
    $(document).on('ajaxComplete', function() {
        initSelect2();
    });
    
    // Expose function for manual initialization
    window.initSelect2 = initSelect2;
    
})(jQuery);
