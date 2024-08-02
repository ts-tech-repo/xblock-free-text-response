"""
Handle view logic for the XBlock
"""
from six import text_type
from xblock.core import XBlock
from xblock.validation import ValidationMessage
from xblock.scorable import ScorableXBlockMixin, Score
try:
    from xblock.utils.resources import ResourceLoader
    from xblock.utils.studio_editable import StudioEditableXBlockMixin
except ModuleNotFoundError:
    # For backward compatibility with releases older than Quince.
    from xblockutils.resources import ResourceLoader
    from xblockutils.studio_editable import StudioEditableXBlockMixin

from .mixins.dates import EnforceDueDates
from .mixins.fragment import XBlockFragmentBuilderMixin
from edx_sga.showanswer import ShowAnswerXBlockMixin
from .mixins.i18n import I18nXBlockMixin
from .models import Credit
from .models import MAX_RESPONSES
from lms.djangoapps.courseware.models import StudentModule
from common.djangoapps.student.models import anonymous_id_for_user
from webob.response import Response

import logging
import json
from submissions import api as submissions_api
from lms.djangoapps.grades.api import signals as grades_signals

log = logging.getLogger(__name__)

#  pylint: disable=no-member
@XBlock.needs('replace_urls')
@XBlock.needs('user')
@XBlock.needs("i18n")
class FreeTextResponseViewMixin(
        I18nXBlockMixin,
        EnforceDueDates,
        XBlockFragmentBuilderMixin,
        StudioEditableXBlockMixin,
        ShowAnswerXBlockMixin, XBlock, ScorableXBlockMixin,
):
    """
    Handle view logic for FreeTextResponse XBlock instances
    """

    loader = ResourceLoader(__name__)
    static_js_init = 'FreeTextResponseView'

    def provide_context(self, context=None):
        """
        Build a context dictionary to render the student view
        """
        context = context or {}
        context = dict(context)
        if user_service := self.runtime.service(self, 'user'):
            is_course_staff = user_service.get_current_user().opt_attrs.get("edx-platform.user_is_staff")
        self.student_id = self.xmodule_runtime.anonymous_student_id
        context.update({
            'display_name': self.display_name,
            'indicator_class': self._get_indicator_class(),
            'nodisplay_class': self._get_nodisplay_class(),
            'problem_progress': self._get_problem_progress(),
            'prompt': self.prompt,
            'student_answer': self.student_answer.replace("\n", "<br>"),
            'is_graded': self.get_score(self.xmodule_runtime.get_real_user(self.student_id)) if self.student_id != "student" else False,
            'is_past_due': self.is_past_due(),
            'used_attempts_feedback': self._get_used_attempts_feedback(),
            'visibility_class': self._get_indicator_visibility_class(),
            'word_count_message': self._get_word_count_message(),
            'display_other_responses': self.display_other_student_responses,
            'other_responses': self.get_other_answers(),
            'user_alert': '',
            'submitted_message': '',
            'loggedin_user' : self.xmodule_runtime.get_real_user(self.student_id) if self.student_id  != "student" else False,
            'is_course_staff' : self.is_course_staff(),
            'block_id' : self.scope_ids.def_id,
            'users_submissions' : self.staff_grading_data(),
            'student_submission' : self.get_student_submission()  if self.student_id  != "student" else {},
        })
        return context

    def _get_indicator_class(self):
        """
        Returns the class of the correctness indicator element
        """
        result = 'unanswered'
        if self.display_correctness and self._word_count_valid():
            if self._determine_credit() == Credit.zero:
                result = 'incorrect'
            else:
                result = 'correct'
        return result

    def _get_nodisplay_class(self):
        """
        Returns the css class for the submit button
        """
        result = ''
        if self.max_attempts > 0 and self.count_attempts >= self.max_attempts:
            result = 'nodisplay'
        return result

    def _word_count_valid(self):
        """
        Returns a boolean value indicating whether the current
        word count of the user's answer is valid
        """
        word_count = len(self.student_answer.split())
        result = self.max_word_count >= word_count >= self.min_word_count
        return result

    def _determine_credit(self):
        #  Not a standard xlbock pylint disable.
        # This is a problem with pylint 'enums and R0204 in general'
        """
        Helper Method that determines the level of credit that
        the user should earn based on their answer
        """
        result = None
        if self.student_answer == '' or not self._word_count_valid():
            result = Credit.zero
        elif not self.fullcredit_keyphrases \
                and not self.halfcredit_keyphrases:
            result = Credit.full
        elif _is_at_least_one_phrase_present(
                self.fullcredit_keyphrases,
                self.student_answer
        ):
            result = Credit.full
        elif _is_at_least_one_phrase_present(
                self.halfcredit_keyphrases,
                self.student_answer
        ):
            result = Credit.half
        else:
            result = Credit.zero
        return result

    def _get_problem_progress(self):
        """
        Returns a statement of progress for the XBlock, which depends
        on the user's current score
        """
        self.score = 0 if self.score is None else self.score
        if self.weight == 0:
            result = ''
        elif self.score == 0.0:
            weight = self.weight
            temp = self.ngettext(f'{weight} point possible',
                                 f'{weight} points possible', weight)
            result = f"({temp})"
        else:
            # scaled_score = self.score * self.weight
            # # No trailing zero and no scientific notation
            # score_string = f'{scaled_score:.15f}'.rstrip('0').rstrip('.')
            # weight = self.weight
            # temp = self.ngettext(f'{score_string}/{weight} point',
            #                      f'{score_string}/{weight} points', weight)
            result = "{} / {}".format(self.score, self.weight)
        return result

    def _get_used_attempts_feedback(self):
        """
        Returns the text with feedback to the user about the number of attempts
        they have used if applicable
        """
        result = ''
        if self.max_attempts > 0:
            result = self.ngettext(
                'You have used {count_attempts} of {max_attempts} submission',
                'You have used {count_attempts} of {max_attempts} submissions',
                self.max_attempts,
            ).format(
                count_attempts=self.count_attempts,
                max_attempts=self.max_attempts,
            )
        return result

    def _get_indicator_visibility_class(self):
        """
        Returns the visibility class for the correctness indicator html element
        """
        if self.display_correctness:
            result = ''
        else:
            result = 'hidden'
        return result

    def _get_word_count_message(self):
        """
        Returns the word count message
        """
        result = self.ngettext(
            "Your response must be "
            "between {min} and {max} word.",
            "Your response must be "
            "between {min} and {max} words.",
            self.max_word_count,
        ).format(
            min=self.min_word_count,
            max=self.max_word_count,
        )
        return result

    def get_other_answers(self):
        """
        Returns at most MAX_RESPONSES answers from the pool.

        Does not return answers the student had submitted.
        """
        student_id = self.get_student_id()
        display_other_responses = self.display_other_student_responses
        shouldnt_show_other_responses = not display_other_responses
        student_answer_incorrect = self._determine_credit() == Credit.zero
        if student_answer_incorrect or shouldnt_show_other_responses:
            return []
        return_list = [
            response
            for response in self.displayable_answers
            if response['student_id'] != student_id
        ]
        return_list = return_list[-(MAX_RESPONSES):]
        return return_list

    @XBlock.json_handler
    def submit(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Processes the user's submission
        """
        # Fails if the UI submit/save buttons were shut
        # down on the previous sumbisson
        if self._can_submit() and data['student_answer'] != "":
            self.student_answer = data['student_answer']
            # Counting the attempts and publishing a score
            # even if word count is invalid.
            self.count_attempts += 1
            # self._compute_score()
            display_other_responses = self.display_other_student_responses
            if display_other_responses and data.get('can_record_response'):
                self.store_student_response()
        result = {
            'status': 'success',
            'problem_progress': self._get_problem_progress(),
            'indicator_class': self._get_indicator_class(),
            'used_attempts_feedback': self._get_used_attempts_feedback(),
            'nodisplay_class': self._get_nodisplay_class(),
            'submitted_message': self._get_submitted_message(),
            'user_alert': self._get_user_alert(
                ignore_attempts=True,
            ),
            'other_responses': self.get_other_answers(),
            'display_other_responses': self.display_other_student_responses,
            'visibility_class': self._get_indicator_visibility_class(),
        }
        student_item_dict = {
                "student_id": self.xmodule_runtime.anonymous_student_id,
                "course_id": str(self.course_id),
                "item_id": str(self.scope_ids.usage_id),
                "item_type": "freetextresponse",
            }
        submissions_api.create_submission(student_item_dict, self.student_answer)
        return result

    @XBlock.json_handler
    def save_reponse(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Processes the user's save
        """
        # Fails if the UI submit/save buttons were shut
        # down on the previous sumbisson
        if data['student_answer'] != "" and (self.max_attempts == 0 or self.count_attempts < self.max_attempts):
            self.student_answer = data['student_answer']
        result = {
            'status': 'success',
            'problem_progress': self._get_problem_progress(),
            'used_attempts_feedback': self._get_used_attempts_feedback(),
            'nodisplay_class': self._get_nodisplay_class(),
            'submitted_message': '',
            'user_alert': self.saved_message,
            'visibility_class': self._get_indicator_visibility_class(),
        }
        return result

    def _get_invalid_word_count_message(self, ignore_attempts=False):
        """
        Returns the invalid word count message
        """
        result = ''
        if (
                (ignore_attempts or self.count_attempts > 0) and
                (not self._word_count_valid())
        ):
            word_count_message = self._get_word_count_message()
            result = self.gettext(
                "Invalid Word Count. {word_count_message}"
            ).format(
                word_count_message=word_count_message,
            )
        return result

    def _get_submitted_message(self):
        """
        Returns the message to display in the submission-received div
        """
        result = ''
        if self._word_count_valid():
            result = self.submitted_message
        return result

    def _get_user_alert(self, ignore_attempts=False):
        """
        Returns the message to display in the user_alert div
        depending on the student answer
        """
        result = ''
        if not self._word_count_valid():
            result = self._get_invalid_word_count_message(ignore_attempts)
        return result

    def _can_submit(self):
        """
        Determine if a user may submit a response
        """
        if self.is_past_due():
            return False
        if self.max_attempts == 0:
            return True
        if self.count_attempts < self.max_attempts:
            return True
        return False

    def _generate_validation_message(self, text):
        """
        Helper method to generate a ValidationMessage from
        the supplied string
        """
        result = ValidationMessage(
            ValidationMessage.ERROR,
            self.gettext(text_type(text))
        )
        return result

    def validate_field_data(self, validation, data):
        """
        Validates settings entered by the instructor.
        """
        if data.weight < 0:
            msg = self._generate_validation_message(
                'Weight Attempts cannot be negative'
            )
            validation.add(msg)
        if data.max_attempts < 0:
            msg = self._generate_validation_message(
                'Maximum Attempts cannot be negative'
            )
            validation.add(msg)
        if data.min_word_count < 1:
            msg = self._generate_validation_message(
                'Minimum Word Count cannot be less than 1'
            )
            validation.add(msg)
        if data.min_word_count > data.max_word_count:
            msg = self._generate_validation_message(
                'Minimum Word Count cannot be greater than Max Word Count'
            )
            validation.add(msg)
        if not data.submitted_message:
            msg = self._generate_validation_message(
                'Submission Received Message cannot be blank'
            )
            validation.add(msg)
    
    @XBlock.handler
    def enter_grade(self, request, suffix=""):
        # pylint: disable=unused-argument
        """
        Persist a score for a student given by staff.
        """
        require(self.is_course_staff())
        score = request.params.get("grade", None)
        module = self.get_student_module(request.params["module_id"])
        if not score:
            return Response(
                json_body=self.validate_score_message(
                    module.course_id, module.student.username
                )
            )

        state = json.loads(module.state)
        # try:
        #     score = int(score)
        # except ValueError:
        #     return Response(
        #         json_body=self.validate_score_message(
        #             module.course_id, module.student.username
        #         )
        #     )

        state["staff_score"] = score
        state["score"] = score
        state["comment"] = request.params.get("comment", "")
        module.state = json.dumps(state)
        module.save()
        log.info(self.scope_ids)
        submissions_api.set_score(request.params["submission_id"], score, self.max_score())
        log.info(
            "enter_grade for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username,
        )

        return Response(json_body=self.staff_grading_data())
    
    @XBlock.handler
    def remove_grade(self, request, suffix=""):
        # pylint: disable=unused-argument
        """
        Reset a students score request by staff.
        """
        require(self.is_course_staff())
        student_id = request.params["student_id"]
        module = self.get_student_module(request.params["module_id"])
        submissions_api.reset_score(student_id, str(self.course_id), str(self.scope_ids.usage_id))
        state = json.loads(module.state)
        state["staff_score"] = None
        state["comment"] = None
        module.grade = None
        module.max_grade = None
        # state["score"] = None
        module.state = json.dumps(state)
        module.save()
        log.info(
            "remove_grade for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username,
        )
        return Response(json_body=self.staff_grading_data())
    
    def staff_grading_data(self):
        submissions = StudentModule.get_state_by_params(self.scope_ids.usage_id.context_key, [self.scope_ids.usage_id])
        users_submissions = []

        for submission in submissions:
            student_submission = self.get_submission(submission.student)
            users_submissions.append({"username" : submission.student.username, "firstname" : submission.student.first_name, "score" : self.get_score(submission.student), "comments" : json.loads(submission.state).get("comment", ""), "module_id" : submission.id, "max_points" : self.weight, "student_answer" : json.loads(submission.state).get("student_answer", "").replace("\n", "<br>"), "submission_id" : student_submission.get("uuid", None) if student_submission else None, "student_id" : anonymous_id_for_user(submission.student, self.course_id) })
        return {"submissions" : users_submissions}
    
    def is_course_staff(self):
        if user_service := self.runtime.service(self, 'user'):
            return user_service.get_current_user().opt_attrs.get("edx-platform.user_is_staff")
        return False
 
    def get_student_module(self, module_id):
        return StudentModule.objects.get(pk=module_id)
    
    def get_submission(self, student=None):

        submissions = submissions_api.get_submissions(
            {
                "student_id": anonymous_id_for_user(student, self.course_id),
                "course_id": str(self.course_id),
                "item_id": str(self.scope_ids.usage_id),
                "item_type": "freetextresponse",
            }
        )
        if submissions:
            # If I understand docs correctly, most recent submission should
            # be first
            return submissions[0]

        return None
    
    def get_student_submission(self):

        student_submission = StudentModule.get_state_by_params(self.scope_ids.usage_id.context_key, [self.scope_ids.usage_id], self.xmodule_runtime.get_real_user(self.xmodule_runtime.anonymous_student_id).id)

        if student_submission:
            return json.loads(student_submission[0].state)

        return {}
    
    def calculate_score(self):
        return Score(self.learner_score, self.max_raw_score())

    def publish_grade(self):
        self._publish_grade(self.calculate_score())
    
    def get_score(self, student=None):
        score = submissions_api.get_score({
                "student_id": anonymous_id_for_user(student, self.course_id),
                "course_id": str(self.course_id),
                "item_id": str(self.scope_ids.usage_id),
                "item_type": "freetextresponse",
            })
        if score:
            return score["points_earned"]

        return None

    def has_submitted_answer(self):
        return self.student_answer
    
    def validate_score_message(
        self, course_id, username
    ):  # lint-amnesty, pylint: disable=missing-function-docstring
        # pylint: disable=no-member
        log.error(
            "enter_grade: invalid grade submitted for course:%s module:%s student:%s",
            course_id,
            self.location,
            username,
        )
        return {"error": "Please enter valid grade"}


def require(assertion):
    if not assertion:
        raise PermissionDenied


def _is_at_least_one_phrase_present(phrases, answer):
    """
    Determines if at least one of the supplied phrases is
    present in the given answer
    """
    answer = answer.lower()
    matches = [
        phrase.lower() in answer
        for phrase in phrases
    ]
    return any(matches)
