$(document).ready(function() {
  $(".identifier").on("click", function(event){
    $(this).parent().find(".details").slideToggle(100);
  });
});

$(document).ready(function() {
  $(".raw").on("click", function(event){
    $(this).parent().find(".rawdata").slideToggle(100);
  });
});
