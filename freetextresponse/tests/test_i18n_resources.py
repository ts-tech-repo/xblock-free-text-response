# -*- coding: utf-8 -*-
"""
Tests for gettext translations and XBlock i18n.
"""
from gettext import GNUTranslations
import ddt
from mock import patch

from django.test import TestCase
import django.utils.translation
from django.utils.translation.trans_real import get_language, translation
from freetextresponse.xblocks import FreeTextResponse

from .tests_utils import get_mo_files, make_xblock


def mock_gettext(source, *_args):
    """
    Mock gettext to avoid loading the .mo file.
    """
    return {
        'Submit':
            'Süßmït',

        'Your response must be between {min} and {max} word.':
            'Ýöür réspönsé müst ßé ßétwéén {min} änd {max} wörd.',

        'Your response must be between {min} and {max} words.':
            'Ýöür réspönsé müst ßé ßétwéén {min} änd {max} wörds.',
    }.get(source, source)


class TestFreeTextResponseI18N(TestCase):
    """
    Ensure the i18n is setup correctly for the XBlock.
    """

    def test_esperanto_translations_in_student_view(self):
        """
        Checks if the template and its context are both correctly translated.
        """
        xblock = make_xblock('freetextresponse', FreeTextResponse, {})
        current_translation = translation(get_language())

        with django.utils.translation.override('eo'), \
                patch.object(current_translation, 'gettext') as gettext, \
                patch.object(current_translation, 'ngettext') as ngettext:

            gettext.side_effect = mock_gettext
            ngettext.side_effect = mock_gettext
            student_view = xblock.student_view()
            student_view_html = student_view.content

        self.assertIn('Süßmït', student_view_html)

        english_text = 'Your response must be between'
        translated_text = 'Ýöür réspönsé müst ßé ßétwéén'
        self.assertNotIn(english_text, student_view_html)
        self.assertIn(translated_text, student_view_html)


@ddt.ddt
class MoFilesTestCase(TestCase):
    """
    Ensure `.mo` files can be parsed and without plural form issues.
    """

    @ddt.data(*get_mo_files())
    def test_mo_file_parsing(self, mo_file_path):
        """
        Check `.mo` files against bad data and plural forms.

        This issue should _not_ happen when running `$ make translations_pull`.

        In case it happened, it can be fixed manually by:
         - Remove the line
           "Plural-Forms: nplurals=INTEGER; plural=EXPRESSION;\n"
           from the offending file
         - Recompile:
           $ cd translations/en/LC_MESSAGES/
           $ msgfmt text.po -o text.mo
        """
        with open(mo_file_path, 'rb') as mo_file_fp:
            # Fails if there's a bad plural form in `.mo` file
            GNUTranslations(mo_file_fp)
