from lmfdb.tests import LmfdbTest
from lmfdb.utils.search_parsing import nf_string_to_label, nf_string_to_min_poly
from lmfdb.number_fields.web_number_field import field_pretty

class NumberFieldTest(LmfdbTest):
    # All tests should pass
    def test_Q(self):
        self.check_args('/NumberField/Q', r'\chi_{1}')
        self.check_args('/NumberField/1.1.1.1', r'\chi_{1}')

    def test_hard_degree10(self):
        self.check_args('/NumberField/10.10.1107649855354064.1', '10T36')
        self.check_args('/NumberField/10.10.138420300533025695415730492558689.1', '10T38')

    def test_hard_degree16(self):
        self.check_args('/NumberField/16.0.13307764731675384304522756096.1', '16T1535')

    def test_search_ramif_cl_deg(self):
        self.check_args('/NumberField/?degree=5&class_group=[2%2C2]&ur_primes=7&discriminant=&ram_quantifier=exactly&ram_primes=2%2C3%2C5', '5.1.27000000000.8')

    def test_abelian_conductor(self):
        self.check_args('/NumberField/5.5.5719140625.2', '275') # conductor

    def test_stuff_not_computed(self):
        self.check_args('/NumberField/23.23.931347256889446325436632107655346061164193665348344821578377438399536607931200329.1', 'ot computed')

    def test_search_poly_mean2parser(self):
        # X^3-4x+2
        self.check_args('/NumberField/?jump=X**3-4x%2B2&search=Go', '3.3.148.1') # label
        # z^3 - 4*z + 2
        self.check_args('/NumberField/?jump=z%5E3+-+4*z%2B2', '3.3.148.1') # label

    def test_search_zeta(self):
        self.check_args('/NumberField/?jump=Qzeta23&search=Go', '[3]') # class group

    def test_search_sqrt(self):
        self.check_args('/NumberField/?jump=Qsqrt-163&search=Go', '41') # minpoly

    def test_search_disc(self):
        self.check_args('/NumberField/?discriminant=1988-2014', '401') # factor of one of the discriminants

    def test_url_label(self):
        self.check_args('/NumberField/2.2.5.1', '0.481211825') # regulator

    def test_url_naturallabel(self):
        self.check_args('/NumberField/Qsqrt5', '0.481211825') # regulator

    def test_url_biquadratic_naturallabel(self):
        self.check_args('/NumberField/Q(sqrt2+sqrt3)', '4.4.2304.1')

    def test_url_cubic_naturallabel(self):
        self.check_args('/NumberField/Qcbrt2', '3.1.108.1')

    def test_url_cubic_naturallabel_parenthesized(self):
        self.assertEqual(nf_string_to_label('Q(cbrt(2))'), nf_string_to_label('Qcbrt2'))

    def test_url_biquadratic_comma_naturallabel(self):
        self.assertEqual(nf_string_to_label('Q(sqrt2,sqrt3)'), nf_string_to_label('Q(sqrt2+sqrt3)'))

    def test_url_quartic_nested_radical_naturallabel(self):
        self.assertEqual(nf_string_to_label('Q(sqrt(1+1*sqrt2))'), nf_string_to_label('x^4-2*x^2-1'))

    def test_url_recursive_nested_surds_and_cbrt(self):
        expr = 'sqrt(3)+sqrt(2+4*sqrt(4)+cbrt(7))'
        self.assertEqual(nf_string_to_min_poly(expr), nf_string_to_min_poly('sqrt(3)+sqrt(10+cbrt(7))'))

    def test_url_multi_generator_comma_form(self):
        self.assertEqual(nf_string_to_label('Q(sqrt2,sqrt3,cbrt2)'), nf_string_to_label('Q(sqrt2+sqrt3+cbrt2)'))

    def test_url_multi_generator_no_cancellation_bug(self):
        self.assertEqual(nf_string_to_label('Q(sqrt2,-sqrt2)'), nf_string_to_label('Qsqrt2'))

    def test_url_i_symbol_support(self):
        self.assertEqual(nf_string_to_min_poly('i'), nf_string_to_min_poly('sqrt(-1)'))
        self.assertEqual(nf_string_to_label('Q(i)'), nf_string_to_label('Q(i+0)'))

    def test_url_zeta_symbol_support(self):
        self.assertEqual(nf_string_to_min_poly('zeta_5'), nf_string_to_min_poly('zeta(5)'))
        self.assertEqual(nf_string_to_label('Q(zeta_5)'), nf_string_to_label('Qzeta5'))

    def test_url_phi_symbol_support(self):
        self.assertEqual(nf_string_to_min_poly('phi'), nf_string_to_min_poly('(1+sqrt(5))/2'))
        self.assertEqual(nf_string_to_label('Q(phi)'), nf_string_to_label('Qsqrt5'))

    def test_field_pretty_triquadratic(self):
        label = nf_string_to_label('Q(sqrt2,sqrt3,sqrt5)')
        self.assertEqual(field_pretty(label), r'\(\Q(\sqrt{2}, \sqrt{3}, \sqrt{5})\)')

    def test_field_pretty_quartic_nested_radical(self):
        label = nf_string_to_label('Q(sqrt(3+sqrt2))')
        self.assertEqual(field_pretty(label), r'\(\Q(\sqrt{3 + \sqrt{2}})\)')

    def test_field_pretty_pure_cubic(self):
        label = nf_string_to_label('Qcbrt2')
        self.assertEqual(field_pretty(label), r'\(\Q(\sqrt[3]{2})\)')

    def test_field_pretty_pure_higher_degree(self):
        label4 = nf_string_to_label('x^4-2')
        label5 = nf_string_to_label('x^5-2')
        self.assertEqual(field_pretty(label4), r'\(\Q(\sqrt[4]{2})\)')
        self.assertEqual(field_pretty(label5), r'\(\Q(\sqrt[5]{2})\)')

    def test_arith_equiv(self):
        self.check_args('/NumberField/7.3.6431296.1', '7.3.6431296.2') # arith equiv field

    def test_sextic_twin(self):
        self.check_args('/NumberField/6.0.10816.1', 'Twin sextic algebra')

    def test_how_computed(self):
        self.check_args('/NumberField/Source', 'Hunter searches')

    def test_galois_group_page(self):
        self.check_args('/NumberField/GaloisGroups', 'abstract group may have')

    def test_imaginary_quadratic_page(self):
        self.check_args('/NumberField/QuadraticImaginaryClassGroups', 'extensive computations')

    def test_discriminants_page(self):
        self.check_args('/NumberField/Source', 'Jones-David Roberts')

    def test_field_labels_page(self):
        self.check_args('/NumberField/FieldLabels', 'with the same signature and absolute value of the')

    def test_url_bad(self):
        self.check_args('/NumberField/junk', 'Error')  # error message

    def test_random_field(self):
        self.check_args('/NumberField/random', 'Discriminant')

    def test_statistics(self):
        self.check_args('/NumberField/stats', 'Class number')

    def test_signature_search(self):
        # Square brackets
        self.check_args('/NumberField/?start=0&degree=6&signature=%5B0%2C3%5D&count=100', '6.0.61131.1')
        self.check_args('/NumberField/?start=0&degree=7&signature=%5B3%2C2%5D&count=100', '7.3.1420409.1')
        # Round brackets
        self.check_args('/NumberField/?start=0&degree=6&signature=%280%2C3%29&count=100', '6.0.61131.1')
        self.check_args('/NumberField/?start=0&degree=7&signature=%283%2C2%29&count=100', '7.3.1420409.1')

    def test_signature_display(self):
        # Verify that signatures are displayed with parentheses, not square brackets
        self.check_args('/NumberField/6.0.61131.1', '(0, 3)')  # degree 6 field with signature (0, 3)
        self.check_args('/NumberField/7.3.1420409.1', '(3, 2)')  # degree 7 field with signature (3, 2)

    def test_relative_class_number(self):
        self.check_args('/NumberField/4.0.1327873600.2', '2108')

    def test_fundamental_units(self):
        self.check_args('NumberField/2.2.10069.1', '43388173')
        self.check_args('NumberField/3.3.10004569.1', '22153437467081345')

    def test_split_ors(self):
        self.check_args('/NumberField/?signature=%5B0%2C3%5D&galois_group=S3', '6.0.177147.2')
        self.check_args('/NumberField/?signature=%5B3%2C0%5D&galois_group=S3', '3.3.229.1')
        self.check_args('/NumberField/?signature=[4%2C0]&galois_group=C2xC2&class_number=3%2C6','4.4.1311025.1')
        self.check_args('/NumberField/?signature=[4%2C0]&galois_group=C2xC2&class_number=6%2C3','4.4.1311025.1')
        self.check_args('/NumberField/?signature=[4%2C0]&galois_group=C2xC2&class_number=5-6%2C3','4.4.485809.1')

    def test_underlying_data(self):
        self.check_args('NumberField/2.2.10069.1', ['Underlying data', 'data/2.2.10069.1'])

    def test_errors(self):
        self.check_args('NumberField/18.0.10490638424...4432.1/download/sage', 'Invalid label')
        self.check_args('NumberField/4.3.2.1/download/sage', 'There is no number field with label 4.3.2.1')

    def test_signature_download(self):
        # Test that signature is downloaded as [r1, r2] not [r2, degree]
        # For degree 2 fields with negative discriminant: signature is [0, 1] (complex)
        # For degree 2 fields with positive discriminant: signature is [2, 0] (real)
        url = ('/NumberField/?download=1'
               '&query=%7B%27degree%27%3A+2%2C+%27%24or%27%3A+%5B%7B%27disc_sign%27%3A+'
               '-1%2C+%27disc_abs%27%3A+%7B%27%24gte%27%3A+1%2C+%27%24lte%27%3A+3%7D%2C+'
               '%27degree%27%3A+2%7D%2C+%7B%27disc_sign%27%3A+1%2C+%27disc_abs%27%3A+'
               '%7B%27%24lte%27%3A+5%2C+%27%24gte%27%3A+1%7D%2C+%27degree%27%3A+2%7D%5D%7D'
               '&degree=2&discriminant=-3-5&showcol=signature&Submit=text')
        page = self.tc.get(url).get_data(as_text=True)
        # Check that signature format is [r1, r2] where:
        # - For imaginary quadratic fields (disc < 0, degree=2): r1=0, r2=1, so signature=[0, 1]
        # - For real quadratic fields (disc > 0, degree=2): r1=2, r2=0, so signature=[2, 0]
        # The bug was that it showed [r2, degree] = [1, 2] or [0, 2] instead
        assert '[0, 1]' in page  # imaginary quadratic field (with space, no quotes)
        assert '[2, 0]' in page  # real quadratic field (with space, no quotes)
        # Make sure we're NOT getting the buggy format [r2, degree]
        assert '[1, 2]' not in page  # wrong format for imaginary quadratic
        assert '[0, 2]' not in page  # wrong format for real quadratic
        # Also ensure we're not getting quoted strings
        assert '"[0, 1]"' not in page
        assert '"[2, 0]"' not in page
