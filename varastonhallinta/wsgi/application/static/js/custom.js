// ----------------------------------------------------------------------------
// advanced search
// ----------------------------------------------------------------------------
$("#advancedSearchSubmit").click(function () {
    if (document.getElementsByClassName("search-input")[0].value
            === "(tarkennettu haku)") {
        $("#table").bootstrapTable("refresh")
    }
    else {
        $("#table").bootstrapTable("resetSearch", "(tarkennettu haku)")
    }
})

function queryParams(params) {
    params.regex_search = document.getElementById("regex_search").value
    params.ignore_case = document.getElementById("ignore_case").checked
    params.numero = [
        document.getElementById("numero_alku").value,
        document.getElementById("numero_loppu").value
        ].join(",")
    params.saapumispvm = [
        document.getElementById("saapumispvm_alku").value,
        document.getElementById("saapumispvm_loppu").value
        ].join(",")
    params.toimituspvm = [
        document.getElementById("toimituspvm_alku").value,
        document.getElementById("toimituspvm_loppu").value
        ].join(",")
    params.hinta = [
        document.getElementById("hinta_alku").value,
        document.getElementById("hinta_loppu").value
        ].join(",")
    params.varausnumero = [
        document.getElementById("varausnumero_alku").value,
        document.getElementById("varausnumero_loppu").value
        ].join(",")
    params.arkistoitu = Array.from(
            document.querySelectorAll("#arkistoitu option:checked")
        ).map(o => o.value).join(",")
    params.sijainti = Array.from(
            document.querySelectorAll("#sijainti option:checked")
        ).map(o => o.value).join(",")
    params.tila = Array.from(
            document.querySelectorAll("#tila option:checked")
        ).map(o => o.value).join(",")
    params.toimitustapa = Array.from(
            document.querySelectorAll("#toimitustapa option:checked")
        ).map(o => o.value).join(",")
    return params
}

// ----------------------------------------------------------------------------
// bootstrap-table custom buttons
// ----------------------------------------------------------------------------
function buttons () {
    return {
        btnAdvancedSearch: {
            text: "Tarkennettu haku",
            icon: "fa-search-plus",
            attributes: {
                id: "tarkennettu_haku",
                title: "Tarkennettu haku",
                "data-toggle": "modal",
                "data-target": "#advancedSearch"
            }
        }
    }
}

// ----------------------------------------------------------------------------
// bootstrap-table formatters
// ----------------------------------------------------------------------------
function operationsFormatter(value, row, index, field) {
    return '<a href="' + value + '/edit" class="btn btn-sm btn-primary">'
           + '<i class="fa fa-edit"></i> Muokkaa</a>'
}

function orderOperationsFormatter(value, row, index, field) {
    return '<a href="' + value + '/order_edit" class="btn btn-sm btn-primary">'
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

$(".input-daterange").datepicker({
    format: "yyyy-mm-dd",
    weekStart: 1,
    todayBtn: "linked",
    language: "fi",
    clearBtn: true
})

// ----------------------------------------------------------------------------
// bootstrap-select settings
// ----------------------------------------------------------------------------
$(".selectpicker").selectpicker({
    iconBase: "fa",
    tickIcon: "fa-check",
    noneSelectedText: "Ei mitään valittuna",
    style: "",
    styleBase: "form-control"
});

// ----------------------------------------------------------------------------
// keyboard shortcuts
// ----------------------------------------------------------------------------
window.focus()
document.addEventListener("keydown", e => {
    if (e.ctrlKey && e.key == "7") {
        $("#tarkennettu_haku").click()
    }
}, false)
