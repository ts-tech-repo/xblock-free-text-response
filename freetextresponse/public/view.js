/* eslint-disable no-unused-vars */
/**
 * Initialize the FreeTextResponse student view
 * @param {Object} runtime - The XBlock JS Runtime
 * @param {Object} element - The containing DOM element for this instance of the XBlock
 * @returns {undefined} nothing
 */
function FreeTextResponseView(runtime, element) {
    /* eslint-enable no-unused-vars */
    'use strict';
  
    var $ = window.jQuery;
    var $element = $(element);
    var $xblocksContainer = $('#seq_content');
    var buttonHide = $element.find('.hide-button');
    var buttonHideTextHide = $('.hide', buttonHide);
    var buttonHideTextShow = $('.show', buttonHide);
    var buttonSubmit = $element.find('.check.Submit');
    var buttonSave = $element.find('.save');
    var usedAttemptsFeedback = $element.find('.action .used-attempts-feedback');
    var problemProgress = $element.find('.problem-progress');
    var submissionReceivedMessage = $element.find('.submission-received');
    var userAlertMessage = $element.find('.user_alert');
    var textareaStudentAnswer = $element.find('.student_answer');
    var textareaParent = textareaStudentAnswer.parent();
    var responseList = $element.find('.response-list');
    var url = runtime.handlerUrl(element, 'submit');
    var urlSave = runtime.handlerUrl(element, 'save_reponse');
    var xblockId = $element.attr('data-usage-id');
    var cachedAnswerId = xblockId + '_cached_answer';
    var problemProgressId = xblockId + '_problem_progress';
    var usedAttemptsFeedbackId = xblockId + '_used_attempts_feedback';
    var gradeSubmissions = $element.find('#grade-submissions-button');
    var enterGradeUrl = runtime.handlerUrl(element, 'enter_grade');
    var removeGradeUrl = runtime.handlerUrl(element, 'remove_grade');
    var gradePopUpIsOpen = false;
    var staffDownloadUrl = runtime.handlerUrl(element, 'staff_download')
    var currentIFrameHeight = null;
  
    if (typeof $xblocksContainer.data(cachedAnswerId) !== 'undefined') {
        textareaStudentAnswer.text($xblocksContainer.data(cachedAnswerId));
        problemProgress.text($xblocksContainer.data(problemProgressId));
        usedAttemptsFeedback.text($xblocksContainer.data(usedAttemptsFeedbackId));
    }
  
    // POLYFILL notify if it does not exist. Like in the xblock workbench.
    runtime.notify = runtime.notify || function () {
        // eslint-disable-next-line prefer-rest-params, no-console
        console.log('POLYFILL runtime.notify', arguments);
    };
    $("#submissions").tablesorter();
    /**
     * Update CSS classes
     * @param {string} newClass - a CSS class name to be used
     * @returns {undefined} nothing
     */
    function setClassForTextAreaParent(newClass) {
        textareaParent.removeClass('correct');
        textareaParent.removeClass('incorrect');
        textareaParent.removeClass('unanswered');
        textareaParent.addClass(newClass);
    }
  
    /**
     * Convert list of responses to an html string
     * @param {Array} responses - a list of Responses
     * @returns {string} a string of HTML to add to the page
     */
    function getStudentResponsesHtml(responses) {
        var html = '';
        var noResponsesText = responseList.data('noresponse');
        responses.forEach(function (item) {
            html += '<li class="other-student-responses">' + item.answer + '</li>';
        });
        html = html || '<li class="no-response">' + noResponsesText + '</li>';
        return html;
    }
  
    /**
     * Display responses, if applicable
     * @param {Object} response - a jQuery HTTP response
     * @returns {undefined} nothing
     */
    function displayResponsesIfAnswered(response) {
        if (!response.display_other_responses) {
            $element.find('.responses-box').addClass('hidden');
            return;
        }
        var responseHTML = getStudentResponsesHtml(response.other_responses);
        responseList.html(responseHTML);
        $element.find('.responses-box').removeClass('hidden');
    }
  
    buttonHide.on('click', function () {
        responseList.toggle();
        buttonHideTextHide.toggle();
        buttonHideTextShow.toggle();
    });
  
    buttonSubmit.on('click', function () {
        buttonSubmit.text(buttonSubmit[0].dataset.checking);
        runtime.notify('submit', {
            message: 'Submitting...',
            state: 'start',
        });
        $.ajax(url, {
            type: 'POST',
            data: JSON.stringify({
                // eslint-disable-next-line camelcase
                student_answer: $element.find('.student_answer').val(),
                // eslint-disable-next-line camelcase
                can_record_response: $element.find('.messageCheckbox').prop('checked'),
            }),
            success: function buttonSubmitOnSuccess(response) {
                usedAttemptsFeedback.text(response.used_attempts_feedback);
                buttonSubmit.addClass(response.nodisplay_class);
                problemProgress.text(response.problem_progress);
                submissionReceivedMessage.text(response.submitted_message);
                buttonSubmit.text(buttonSubmit[0].dataset.value);
                userAlertMessage.text(response.user_alert);
                buttonSave.addClass(response.nodisplay_class);
                setClassForTextAreaParent(response.indicator_class);
                displayResponsesIfAnswered(response);
  
                $xblocksContainer.data(cachedAnswerId, $element.find('.student_answer').val());
                $xblocksContainer.data(problemProgressId, response.problem_progress);
                $xblocksContainer.data(usedAttemptsFeedbackId, response.used_attempts_feedback);
  
                runtime.notify('submit', {
                    state: 'end',
                });
            },
            error: function buttonSubmitOnError() {
                runtime.notify('error', {});
            },
        });
        return false;
    });
  
    buttonSave.on('click', function () {
        buttonSave.text(buttonSave[0].dataset.checking);
        runtime.notify('save', {
            message: 'Saving...',
            state: 'start',
        });
        $.ajax(urlSave, {
            type: 'POST',
            data: JSON.stringify({
                // eslint-disable-next-line camelcase
                student_answer: $element.find('.student_answer').val(),
            }),
            success: function buttonSaveOnSuccess(response) {
                buttonSubmit.addClass(response.nodisplay_class);
                buttonSave.addClass(response.nodisplay_class);
                usedAttemptsFeedback.text(response.used_attempts_feedback);
                problemProgress.text(response.problem_progress);
                submissionReceivedMessage.text(response.submitted_message);
                buttonSave.text(buttonSave[0].dataset.value);
                userAlertMessage.text(response.user_alert);
  
                $xblocksContainer.data(cachedAnswerId, $element.find('.student_answer').val());
                $xblocksContainer.data(problemProgressId, response.problem_progress);
                $xblocksContainer.data(usedAttemptsFeedbackId, response.used_attempts_feedback);
  
                runtime.notify('save', {
                    state: 'end',
                });
            },
            error: function buttonSaveOnError() {
                runtime.notify('error', {});
            },
        });
        return false;
    });
  
    textareaStudentAnswer.on('keydown', function () {
  
        // Reset Messages
        submissionReceivedMessage.text('');
        userAlertMessage.text('');
        setClassForTextAreaParent('unanswered');
    });
    
    function updateIframe() {
      if (window.parent !== window   && !currentIFrameHeight) {
        currentIFrameHeight = $("body").height()
        addMaxHeightInIframe()
        if (currentIFrameHeight < 600) {
          sendResizeMessage(600)
        }
      }
    }
  
    function addMaxHeightInIframe() {
      $(".grade-submission").css("max-height", "600px")
    }
  
    function sendResizeMessage(height) {
      // This blocks checks to see if the xBlock is part 
      // of Learning MFE
      if (window.parent !== window) {
        window.parent.postMessage({
          type: 'plugin.resize',
          payload: {
            height: height,
          }
        }, document.referrer
        );
      }
    }
  
    gradeSubmissions.leanModal().on('click', function () {
        var section_id = gradeSubmissions.attr("href");
        console.log($(section_id))
        $(section_id).show();
        updateIframe();
  
    })
  
    $(element).find('.enter-grade-button')
        .leanModal({ closeButton: '#enter-grade-cancel' })
        .on('click', handleGradeEntry);
  
    function gradeFormError(error) {
        var form = $(element).find("#enter-grade-form");
        form.find('.error').html(error);
        }
  
    function handleGradeEntry() {
        var row = $(this).parents("tr");
        console.log(row.find("td:eq(3)").text())
        var form = $(element).find("#enter-grade-form");
        $(element).find('#student-name').text(`${row.find("td:eq(1)").text()} (${row.find("td:eq(0)").text()})`);
        form.find('#module_id-input').val(row.find("td:eq(5)").text());
        form.find('#grade-input').val(row.find("td:eq(3)").text().split("/")[0]);
        form.find('#comment-input').text(row.find("td:eq(4)").text());
        form.find('#comment-input').val(row.find("td:eq(4)").text());
        console.log(row.find("td:eq(2)").text())
        form.find("#student_answer").html(row.find("td:eq(2)").text())
        form.find('#submission_id-input').val(row.find("td:eq(8)").text());
        
        form.find('#remove-grade').prop('disabled', false);
        form.find('.ccx-enter-grade-spinner').hide();
        $("#lean_overlay").show()
        form.off('submit').on('submit', function (event) {
            var max_score = row.parents('#grade-info').data('max_score');
            var score = Number(form.find('#grade-input').val());
            event.preventDefault();
            if (isNaN(score)) {
            gradeFormError('<br/>' + gettext('Grade must be a number.'));
          //   } else if (score !== parseInt(score)) {
          //   gradeFormError('<br/>' + gettext('Grade must be an integer.'));
            } else if (score < 0) {
            gradeFormError('<br/>' + gettext('Grade must be positive.'));
            } else if (score > max_score) {
            gradeFormError('<br/>' + interpolate(gettext('Maximum score is %(max_score)s'), { max_score: max_score }, true));
            } else {
            // No errors
            form.find('.ccx-enter-grade-spinner').show();
            $.post(enterGradeUrl, form.serialize())
                .success(renderStaffGrading)
                .fail(function () {
                form.find('.ccx-enter-grade-spinner').hide();
                });
            }
            $("#submissions").tablesorter();
        });
        form.find('#remove-grade').off('click').on('click', function (event) {
            $(this).prop('disabled', true);
            form.find('.ccx-enter-grade-spinner').show();
            var url = removeGradeUrl + '?module_id=' +
            row.find("td:eq(5)").text() + '&student_id=' +
            row.find("td:eq(6)").text();
            event.preventDefault();
            if (row.find("td:eq(3)").text()) {
            // if there is no grade then it is pointless to call api.
            $.get(url).success(renderStaffGrading).fail(function () {
                $(this).prop('disabled', false);
                form.find('.ccx-enter-grade-spinner').hide();
            });
            } else {
            gradeFormError('<br/>' + gettext('No grade to remove.'));
		    form.find('.ccx-enter-grade-spinner').hide();
            }
            $("#submissions").tablesorter();
        });
        form.find('#enter-grade-cancel').on('click', function () {
            setTimeout(function () {
            $('#grade-submissions-button').click();
            gradeFormError('');
            gradePopUpIsOpen = false
            }, 225);
            $("#submissions").tablesorter();
        });
        gradePopUpIsOpen = true;
        }
  
        function renderStaffGrading(data) {
            console.log(data)
            if (data.hasOwnProperty('error')) {
              gradeFormError(data['error']);
            } else {
              gradeFormError('');
              $('.grade-modal').hide();
            }
      
            if (data.display_name !== '') {
              $('.sga-block .display_name').html(data.display_name);
            }
      
            // Add download urls to template context
            data.downloadUrl = staffDownloadUrl;
            if("error" in data) {
                $(element).find('.ccx-enter-grade-spinner').hide();
            }
            else{
                data["submissions"].map(function (submission) {
                    console.log($(element).find('#grade-info #grade-' + submission.module_id))
                    if(submission.score != null) {
                        $(element).find('#grade-info #grade-' + submission.module_id).text((submission.score) + "/" + (submission.max_points));
                        $(element).find('#grade-info #comment-' + submission.module_id).text(submission.comments);
                    }else {
                        $(element).find('#grade-info #grade-' + submission.module_id).text("");
                        $(element).find('#grade-info #comment-' + submission.module_id).text("");
                    }
                    
                    
                  });
  
            }
            $("#submissions").tablesorter();
            
          }
          $(element).find('.enter-grade-button')
          .leanModal({ closeButton: '#enter-grade-cancel' })
          .on('click', handleGradeEntry);
  
  }
  
  
  function exportTableToExcel(filename){
    $("#submissions").table2excel({
        //Exclude CSS class specific to this plugin
        exclude: ".hide_row",
        name: "Free Text Responses",
        filename: filename,
        columns: [0, 1, 2, 3, 4]
    });
  }
