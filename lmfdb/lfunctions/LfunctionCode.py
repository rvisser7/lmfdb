"""
Code snippets (Sage, Pari/GP, Magma) for L-functions.

An L-function in the database does not carry enough Dirichlet coefficients to
be evaluated everywhere, so the snippets construct it from one of its origins
(an elliptic curve, a genus 2 curve, a Dirichlet character, ...), using the
L-function constructors of Pari (also used from Sage) and Magma.  Once the
L-function L is defined, the remaining snippets do not depend on the origin.

The snippets themselves live in code.yaml in this directory.
"""

import copy
import os
from ast import literal_eval

import yaml
from sage.all import ZZ, QQ, PolynomialRing

from lmfdb import db
from lmfdb.utils import coeff_to_poly

# Languages for which snippets are provided, in the order used by the yaml file
LANGS = ['sage', 'pari', 'magma']

# Order of the snippets in the downloaded code
sorted_code_names = ['lfunction', 'evaluate', 'dirichlet_coeffs', 'functional_equation',
                     'conductor', 'sign', 'rank', 'special_value', 'euler_factor',
                     'zeros', 'plot']

# If an L-function has several origins, the snippets are built from the first
# supported origin in this list (simplest and fastest constructions first).
ORIGIN_PRIORITY = ['EllipticCurveQ', 'Genus2CurveQ', 'Dirichlet', 'NumberField',
                   'ClassicalModularForm', 'EllipticCurveNF']

_yaml_cache = None


def _code_yaml():
    global _yaml_cache
    if _yaml_cache is None:
        _curdir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_curdir, "code.yaml")) as F:
            _yaml_cache = yaml.load(F, Loader=yaml.FullLoader)
    return copy.deepcopy(_yaml_cache)


def _fill(s, data):
    """
    Replace the placeholders {key} in the string s by data[key].
    Unlike str.format, braces not corresponding to a key in data are left alone,
    so {lang} and {label} survive for CodeSnippet.build_frontmatter.
    """
    for key, val in data.items():
        s = s.replace('{' + key + '}', str(val))
    return s


def parse_origin_url(url):
    """
    Given the url of an L-function instance (as in lfunc_instances), return a
    triple (origin_type, origin_label, args) where args are the arguments of the
    corresponding data function below, or None if the origin is not supported.

    EXAMPLES::

        sage: parse_origin_url('EllipticCurve/Q/11/a')
        ('EllipticCurveQ', '11.a', ('11.a',))
        sage: parse_origin_url('ModularForm/GL2/Q/holomorphic/7/3/b/a/6/1')
        ('ClassicalModularForm', '7.3.b.a', ('7.3.b.a',))
    """
    parts = url.strip('/').split('/')
    if parts[0] == 'EllipticCurve' and len(parts) in [4, 5]:
        if parts[1] == 'Q':
            label = '.'.join(parts[2:4])
            return ('EllipticCurveQ', label, (label,))
        label = '-'.join(parts[1:4])
        return ('EllipticCurveNF', label, (label,))
    if parts[0] == 'Genus2Curve' and len(parts) in [4, 6] and parts[1] == 'Q':
        label = '.'.join(parts[2:4])
        return ('Genus2CurveQ', label, (label,))
    if parts[:2] == ['Character', 'Dirichlet'] and len(parts) == 4:
        modulus, number = int(parts[2]), int(parts[3])
        return ('Dirichlet', f'{modulus}.{number}', (modulus, number))
    if parts[0] == 'NumberField' and len(parts) == 2:
        return ('NumberField', parts[1], (parts[1],))
    if parts[:4] == ['ModularForm', 'GL2', 'Q', 'holomorphic'] and len(parts) in [8, 10]:
        label = '.'.join(parts[4:8])
        return ('ClassicalModularForm', label, (label,))
    return None


###############################################################################
# Data for each origin: a dictionary of values for the placeholders in the
# corresponding entry of code.yaml, or None if snippets are not available.
###############################################################################

def ecq_data(iso_label):
    ainvs = db.ec_curvedata.lucky({'lmfdb_iso': iso_label, 'lmfdb_number': 1}, 'ainvs')
    if ainvs is None:
        return None
    return {'ainvs': str([int(a) for a in ainvs])}


def ecnf_data(class_label):
    E = db.ec_nfcurves.lookup(class_label + '1', projection=['field_label', 'ainvs'])
    if E is None:
        return None
    coeffs = db.nf_fields.lookup(E['field_label'], projection='coeffs')
    if coeffs is None:
        return None
    # each a-invariant is stored as a comma-separated list of coefficients
    # with respect to the power basis, a-invariants separated by semicolons
    ainvs = [f"[{ai}]" for ai in E['ainvs'].split(";")]
    return {'field_coeffs': str([int(c) for c in coeffs]),
            'sage_ainvs': "[" + ",".join(f"K({ai})" for ai in ainvs) + "]",
            'magma_ainvs': "[" + ",".join(f"K!{ai}" for ai in ainvs) + "]",
            'pari_ainvs': "[" + ",".join(f"Polrev({ai})" for ai in ainvs) + "]"}


def g2c_data(class_label):
    from lmfdb.genus2_curves.web_g2c import magma_cond_option
    C = db.g2c_curves.lucky({'class': class_label},
                            projection=['eqn', 'cond', 'abs_disc', 'bad_lfactors'],
                            sort=['label'])
    if C is None:
        return None
    f, h = literal_eval(C['eqn'])
    bad_lfactors = literal_eval(C['bad_lfactors'])
    cond = ZZ(C['cond'])
    data = {'f': str(f), 'h': str(h),
            'magma_cond_option': magma_cond_option({'cond': cond,
                                                    'abs_disc': ZZ(C['abs_disc']),
                                                    'bad_lfactors': bad_lfactors}),
            'pari_fix2': '', 'sage_fix2': ''}
    if cond % 2 == 0:
        # Pari's lfungenus2 does not always determine the conductor exponent
        # and the Euler factor at 2 (it then prints a warning), so we put in
        # the conductor and bad Euler factors from the database.
        R = PolynomialRing(ZZ, 'x')
        bad = "[" + ", ".join(f"[{p}, 1/({R(coeffs)})]" if R(coeffs).degree() > 0 else f"[{p}, 1]"
                              for p, coeffs in bad_lfactors) + "]"
        explanation = ("Pari may not determine the conductor exponent at 2, "
                       "so we insert the conductor and bad Euler factors:")
        data['pari_fix2'] = f"\n\\\\ {explanation}\nL[5] = {cond}; L[1][2][2] = {bad};"
        data['sage_fix2'] = f"\n# {explanation}\nLdata[4] = {cond}; Ldata[0][1][1] = pari('{bad}')"
    return data


def dirichlet_data(modulus, number):
    return {'modulus': modulus, 'number': number}


def nf_data(label):
    coeffs = db.nf_fields.lookup(label, projection='coeffs')
    if coeffs is None or len(coeffs) <= 2:
        # Q itself is covered by the Dirichlet character 1.1
        return None
    return {'poly': str(coeff_to_poly(coeffs))}


def cmf_data(label):
    nf = db.mf_newforms.lookup(label, projection=['dim', 'traces', 'conrey_index', 'level',
                                                  'weight', 'space_label'])
    # Only newforms with rational coefficients for now: for these the
    # traces are the coefficients, and there is a single embedding.
    if nf is None or nf['dim'] != 1 or not nf['traces']:
        return None
    # The trace bound is the number of traces needed to distinguish the
    # newforms in the space
    trace_bound = db.mf_newspaces.lookup(nf['space_label'], projection='trace_bound') or 0
    nterms = min(max(trace_bound, 10), len(nf['traces']))
    level, weight, conrey = nf['level'], nf['weight'], nf['conrey_index']
    if conrey == 1:
        magma_space = f"S := CuspForms(Gamma0({level}), {weight});"
    else:
        magma_space = ("// Please install CHIMP (https://github.com/edgarcosta/CHIMP) if you want to run this code\n"
                       f'chi := DirichletCharacter("{level}.{conrey}");\n'
                       f"S := CuspForms(chi, {weight});")
    data = {'level': level, 'weight': weight, 'conrey_index': conrey,
            'nterms': nterms, 'an': str([int(a) for a in nf['traces'][:nterms]]),
            'magma_space': magma_space}
    if weight == 1:
        # Magma's support for weight 1 forms is limited
        data['skip_langs'] = ['magma']
    return data


DATA_FUNCTIONS = {'EllipticCurveQ': ecq_data,
                  'EllipticCurveNF': ecnf_data,
                  'Genus2CurveQ': g2c_data,
                  'Dirichlet': dirichlet_data,
                  'NumberField': nf_data,
                  'ClassicalModularForm': cmf_data}


###############################################################################
# Assembling the snippets
###############################################################################

def build_code(origin_type, origin_label, data, motivic_weight, rank=None):
    """
    Return the dictionary of code snippets (in the format expected by
    CodeSnippet) for an L-function of the given origin, with the given motivic
    weight and order of vanishing at the central point.
    """
    raw = _code_yaml()
    origin = raw['origins'][origin_type]
    data = dict(data)
    skip_langs = data.pop('skip_langs', [])
    langs = [lang for lang in LANGS
             if origin['lfunction'].get(lang) and lang not in skip_langs]

    center = QQ(motivic_weight + 1) / 2
    data['center'] = center
    data['origin_label'] = origin_label
    data['origin'] = _fill(origin['description'], data)
    if rank:
        data['rank'] = rank
        data['sage_factorial'] = f"/factorial({rank})" if rank > 1 else ""
        data['pari_factorial'] = f"/{rank}!" if rank > 1 else ""
        data['magma_factorial'] = f"/Factorial({rank})" if rank > 1 else ""

    code = {'prompt': {lang: raw['prompt'][lang] for lang in langs},
            'frontmatter': {key: _fill(val, data) for key, val in raw['frontmatter'].items()}}

    for name in sorted_code_names:
        if name == 'lfunction':
            item = dict(origin['lfunction'])
        else:
            # A nonzero central value is computed directly; otherwise we give
            # the leading coefficient of the Taylor expansion
            item = dict(raw['special_value_derivative' if name == 'special_value' and rank else name])
            for lang, snippet in origin.get(name, {}).items():
                if snippet is None:
                    item.pop(lang, None)
                else:
                    item[lang] = snippet
        snippets = {lang: _fill(item[lang], data) for lang in langs if item.get(lang)}
        if snippets:
            snippets['comment'] = _fill(item['comment'], data)
            code[name] = snippets
        else:
            code[name] = None
    return code


def lfunction_code(label, instances, motivic_weight, rank=None):
    """
    Return the code snippets for the L-function with the given label, whose
    origins are given by the list `instances` (rows of lfunc_instances),
    or None if no origin is supported.
    """
    if motivic_weight is None or motivic_weight == '':
        return None
    origins = [parse_origin_url(instance['url']) for instance in instances]
    origins = [origin for origin in origins if origin is not None]
    for origin_type in ORIGIN_PRIORITY:
        for typ, origin_label, args in sorted(origins):
            if typ != origin_type:
                continue
            data = DATA_FUNCTIONS[typ](*args)
            if data is not None:
                return build_code(typ, origin_label, data, motivic_weight, rank)
    return None
