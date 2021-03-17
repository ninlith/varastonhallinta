// ----------------------------------------------------------------------------
// bootstrap-table formatters
// ----------------------------------------------------------------------------
function operationsFormatter(value, row, index, field) {
    return '<a href="' + value + '/edit" class="btn btn-sm btn-primary">'
           + '<i class="fa fa-edit"></i> Muokkaa</a>'
}

// ----------------------------------------------------------------------------
// bootstrap alert autoclose, https://stackoverflow.com/a/38837640
// ----------------------------------------------------------------------------
$(function() {
    var alert = $("div.alert[auto-close]")
    alert.each(function() {
        var that = $(this)
        var time_period = that.attr("auto-close")
        setTimeout(function() {
            that.alert("close")
        }, time_period)
    })
})

// ----------------------------------------------------------------------------
// bootstrap-datepicker settings
// ----------------------------------------------------------------------------
$("#datepicker,#datepicker2").datepicker({
    format: "yyyy-mm-dd",
    weekStart: 1,
    todayBtn: "linked",
    language: "fi",
})

// ----------------------------------------------------------------------------
// keyboard shortcuts
// ----------------------------------------------------------------------------
/*
window.focus()
document.addEventListener("keydown", e => {
    if (e.ctrlKey && e.key == "p") {
        window.print()
    }
    else if(e.ctrlKey && e.key == "r" || e.key == "F5") {
        location.reload()
    }
    else if(e.ctrlKey && e.key == "s") {
        console.log("save")
    }
    else if(e.ctrlKey && e.key == "f") {
        console.log("find")
    }
    else if(e.altKey && e.key == "ArrowLeft") {
        window.history.back()
    }
    else if(e.altKey && e.key == "ArrowRight") {
        window.history.forward()
    }
    else if(e.altKey && e.key == "Home") {
        window.location.assign("/")
    }
}, false)
*/
