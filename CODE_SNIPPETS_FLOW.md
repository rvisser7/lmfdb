# Code Snippet Flow in LMFDB: Complete Examples

This document shows how code snippets are created, processed, and rendered in templates, using real examples from the codebase.

## 1. THE COMPLETE FLOW

```
code.yaml (YAML definitions)
    ↓
get_code() / code_snippets() (Python method on WebObject)
    ↓
code dict passed to template context
    ↓
place_code() Jinja2 macro in template
    ↓
CodeSnippet.place_code() (Python class method)
    ↓
HTML with code boxes and language switching
```

---

## 2. EXAMPLE 1: GENUS 2 CURVES (Simpler Pattern)

### Step 1: Define code.yaml

File: `lmfdb/genus2_curves/code.yaml`

```yaml
prompt:
  sage:   'sage'
  pari:   'gp'
  magma:  'magma'

frontmatter:
  all: |
    {lang} code for working with genus 2 curve {label}.

curve:
  comment: Define the curve
  magma: |
    R<x> := PolynomialRing(Rationals());
    fh := %s;
    f := R![a : a in fh[1]];
    h := R![a : a in fh[2]];
    C := HyperellipticCurve(f, h);

aut:
  comment: Automorphism group
  magma: AutomorphismGroup(C);

jacobian:
  comment: Jacobian
  magma: J := Jacobian(SimplifiedModel(C));

cond:
  comment: Conductor
  magma: Conductor(LSeries(C));

disc:
  comment: Discriminant
  magma: Discriminant(C);
```

**Key properties exposed to templates:**
- `prompt`: Maps language codes to display strings (e.g., `magma → 'magma'`)
- `comment`: Human-readable description for each code block
- Code for each language: `magma`, `sage`, `pari`, etc.

### Step 2: Python Class Loads and Processes code.yaml

File: `lmfdb/genus2_curves/web_g2c.py` (lines 1154-1165)

```python
class WebG2C():
    def get_code(self):
        if self._code is None:
            # read in code.yaml from current directory:
            _curdir = os.path.dirname(os.path.abspath(__file__))
            self._code = yaml.load(open(os.path.join(_curdir, "code.yaml")), 
                                   Loader=yaml.FullLoader)

            # Fill in placeholders for this specific curve:
            for lang in ['magma']:  # TODO: 'sage', 'pari',
                self._code['curve'][lang] = self._code['curve'][lang] % (self.data['min_eqn'])

        return self._code
```

**What happens:**
- Loads YAML dict with structure: `{'prompt': {...}, 'curve': {...}, 'aut': {...}, ...}`
- Fills in placeholders (e.g., `%s` becomes actual curve equation)
- Returns dict like:
  ```python
  {
    'prompt': {'sage': 'sage', 'pari': 'gp', 'magma': 'magma'},
    'curve': {
        'comment': 'Define the curve',
        'magma': 'R<x> := PolynomialRing(Rationals()); fh := [1,2,3,...];'
    },
    'aut': {'comment': ..., 'magma': ...},
    ...
  }
  ```

### Step 3: Pass to Template

File: `lmfdb/genus2_curves/main.py` (route handler)

The route handler gets the WebG2C object and passes it to the template context. The template receives:
- `code = C.get_code()` - the dict from Step 2

### Step 4: Template Macro Definition

File: `lmfdb/templates/homepage.html` (lines 1-6)

```html
{% macro place_code(item, is_top_snippet=False) %}
{% if code and code[item] %}
{{ CodeSnippet(code, item).place_code(is_top_snippet=is_top_snippet) }}
{% endif %}
{% endmacro %}
```

**What happens:**
- `code` is the dict passed from Python
- `item` is the key (e.g., `'curve'`, `'cond'`, `'disc'`)
- Creates a `CodeSnippet` object with: `code` dict + `item` name
- Calls `CodeSnippet.place_code()` to render HTML

### Step 5: Template Uses Macro

File: `lmfdb/genus2_curves/templates/g2c_curve.html` (lines 51, 56, 59)

```html
<p>{{ place_code('curve', is_top_snippet=True) }}{{place_code('simple_curve')}}</p>

<table>
<tr><td>Conductor:</td><td>{{ data.cond }}</td>
    <td>{{place_code('cond')}}</td>
</tr>
<tr><td>Discriminant:</td><td>{{ data.disc }}</td>
    <td>{{place_code('disc')}}</td>
</tr>
</table>
```

**What happens:**
- `place_code('curve', is_top_snippet=True)` renders the curve definition code
- `place_code('cond')` renders the conductor code (inline)
- `place_code('disc')` renders the discriminant code (inline)

### Step 6: CodeSnippet Class Renders HTML

File: `lmfdb/utils/place_code.py` (lines 12-76)

```python
class CodeSnippet():
    """ Utility class for displaying code snippets on lmfdb pages """
    
    def __init__(self, code, item=None, pre="", post=""):
        """
        code: dict loaded from code.yaml
        item: key name (e.g., 'curve', 'cond')
        pre/post: optional HTML wrapping (useful for table cells)
        """
        self.code = code
        self.item = item
        
        # Extract available languages from 'prompt' key
        if 'prompt' in code:
            self.langs = sorted(code['prompt'])  # e.g., ['magma', 'pari', 'sage']
        elif 'show' in code:
            self.langs = sorted(code['show'])
        else:
            self.langs = []
        
        self.comments = {'magma': '//', 'sage': '#', 'gp': '\\\\', ...}
        self.full_names = {"pari": "Pari/GP", "sage": "SageMath", ...}

    def place_code(self, is_top_snippet=False):
        """Return HTML string which displays code in code box"""
        if self.item is None:
            raise ValueError("No code to place, please init with code item")
        
        item = self.item
        snippet_str = self.pre  # Start with pre-HTML if provided
        code = self.code
        
        if code[item]:
            # For each language available for this item
            for L in code[item]:
                if isinstance(code[item][L], str):
                    # Split code into lines and escape HTML
                    lines = code[item][L].split('\n')[:-1] if '\n' in code[item][L] else [code[item][L]]
                    lines = [line.replace("<", "&lt;").replace(">", "&gt;") for line in lines]
                else:
                    lines = code[item][L]
                
                # Get prompt text (e.g., 'magma' or custom like 'sage')
                prompt = code['prompt'][L] if 'prompt' in code and L in code['prompt'] else L
                
                # CSS class includes language for show/hide
                class_str = " ".join([L, 'nodisplay', 'codebox'])
                
                # Adjust width for top snippets
                if is_top_snippet:
                    max_width_style = " max-width: 50%;"
                else:
                    max_width_style = " max-width: 1200px;"
                
                # Build HTML with copy button
                snippet_str += f"""
    <div class="{class_str}" style="user-select: none; margin-bottom: 12px; align-items: baseline; {max_width_style}">
        <span class="raw-tset-copy-btn" onclick="copycode(this)"><img alt="Copy content" class="tset-icon"></span>
        <span class="prompt">{prompt}:</span><span class="code">{sep.join(lines)}</span>
        <div style="margin: 0; padding: 0; height: 0;">&nbsp;</div>
    </div>
    """
        return Markup(snippet_str + self.post)  # Markup makes HTML safe

    def show_commands_box(self):
        """Display 'Show commands' box for toggling between languages"""
        # Generates JavaScript that hides/shows code based on language selection
        box_str = '<div align="right">Show commands: '
        lang_strs = []
        for lang in self.langs:
            name = self.full_names.get(lang, lang)
            lang_strs.append(rf"""<a onclick="show_code('{lang}',{self.langs}); return false" href='#'>{name}</a>""")
        box_str += " / ".join(lang_strs) + "</div>"
        
        js_str = r"""
        <script>
        var cur_lang = null;
        function show_code(new_lang, langs) {
           for(var lang of langs){$('.'+lang).hide()}
            if (cur_lang == new_lang) {
              cur_lang = null;
            } else {
              $('.'+new_lang).show();
              $('.'+new_lang).css('display','inline-flex');
              cur_lang = new_lang;
            }
        }
        </script>
        """
        return js_str + box_str
```

---

## 3. EXAMPLE 2: ABSTRACT GROUPS (Complex Pattern with Computed Snippets)

This shows how to build code snippets with **computed data** from the object.

### Step 1: Define code.yaml

File: `lmfdb/groups/abstract/code.yaml` (lines 1-100)

```yaml
prompt:
  magma: 'magma'
  gap: 'gap'
  sage: 'sage'
  sage_gap: 'sage'

presentation:
  comment: Define the group with the given generators and relations
  magma: G := PCGroup({pccodelist}); {gens} := Explode({used_gens}); AssignNames(~G, {magma_assign});
  gap: G := PcGroupCode({pccode},{ordgp}); {gap_assign}
  sage: |
    # This uses Sage's interface to GAP
    G = gap.new('PcGroupCode({pccode},{ordgp})'); {sage_gap_assign}

permutation:
  comment: Define the group as a permutation group
  magma: G := PermutationGroup< {deg} | {perms} >;
  gap: G := Group( {perms} );
  sage: G = PermutationGroup([{perms_sage}])

GLZ:
  comment: Define the group as a matrix group with coefficients in Z
  magma: G := MatrixGroup< {nZ}, Integers() | {LZ} >;
  gap: G := Group({LZsplit});
  sage: |
    MS = MatrixSpace(Integers(), {nZ}, {nZ})
    G = MatrixGroup({LZsage})

order:
  comment: Order of the group
  magma: Order(G);
  gap: Order(G);
  sage: G.order()
```

**Note:** Uses **placeholders** like `{pccode}`, `{perms}`, `{nZ}` which get filled from object data.

### Step 2: Build Code Dict Dynamically

File: `lmfdb/groups/abstract/web_groups.py` (lines 2872-3115)

```python
@cached_method
def code_snippets(self):
    """Build code snippets dict from YAML + object data"""
    if self.live():
        return
    
    # Load YAML template
    _curdir = os.path.dirname(os.path.abspath(__file__))
    code = yaml.load(open(os.path.join(_curdir, "code.yaml")), 
                     Loader=yaml.FullLoader)
    
    # Initialize 'show' dict for each language (used for show_commands_box)
    code['show'] = {lang: '' for lang in code['prompt']}
    
    # Extract PC representation data from database
    if "PC" in self.representations:
        gens = self.presentation_raw(as_str=False)
        pccodelist = self.representations["PC"]["pres"]
        pccode = self.representations["PC"]["code"]
        ordgp = self.order
        used_gens = create_gens_list(self.representations["PC"]["gens"])
        gap_assign = create_gap_assignment(self.representations["PC"]["gens"])
        magma_assign = create_magma_assignment(self)
        sage_gap_assign = create_sage_gap_assignment(self.representations["PC"]["gens"])
    else:
        gens, pccodelist, pccode = None, None, None
        ...
    
    # Extract permutation representation data
    if "Perm" in self.representations:
        rdata = self.representations["Perm"]
        perms = ", ".join(self.decode_as_perm(g, as_str=True) for g in rdata["gens"])
        perms_sage = "'"+("', '".join(...))+"'"
        deg = rdata["d"]
    else:
        perms, perms_sage, deg = None, None, None
    
    # Extract GLZ (integer matrices) representation data
    if "GLZ" in self.representations:
        nZ = self.representations["GLZ"]["d"]
        LZ = [self.decode_as_matrix(g, "GLZ", ListForm=True) for g in self.representations["GLZ"]["gens"]]
        LZsplit = [split_matrix_list(..., nZ) for g in self.representations["GLZ"]["gens"]]
        LZsage = "["+", ".join([...]) + "]"
    else:
        nZ, LZ, LZsplit, LZsage = None, None, None, None
    
    # ... similar for GLFp, GLZN, GLZq, GLFq ...
    
    # Create data dict with all computed values
    data = {
        'gens': gens, 'pccodelist': pccodelist, 'pccode': pccode,
        'ordgp': ordgp, 'used_gens': used_gens, 'gap_assign': gap_assign,
        'magma_assign': magma_assign, 'deg': deg, 'perms': perms,
        'perms_sage': perms_sage, 'nZ': nZ, 'nFp': nFp, ...
        'LZ': LZ, 'LFp': LFp, ...
        'LZsplit': LZsplit, 'LFpsplit': LFpsplit, ...
        'LZsage': LZsage, 'LFpsage': LFpsage, ...
    }
    
    # FORMAT the templates: Replace {placeholder} with actual data
    for prop in code:
        for lang in code[prop]:
            code[prop][lang] = code[prop][lang].format(**data)
    
    # SPECIAL: Create 'code_description' for top code snippet
    # (uses SmallGroup, CyclicGroup, SymmetricGroup, etc. for best representation)
    code['code_description'] = dict()
    
    if self.cyclic:
        code['code_description']['magma'] = "G := CyclicGroup("+str(self.order)+");"
        code['code_description']['gap'] = "G := CyclicGroup("+str(self.order)+");"
        code['code_description']['sage'] = "G = CyclicPermutationGroup("+str(self.order)+")"
    elif self.name[0] == 'S' and self.name[1:].isdigit():
        code['code_description']['magma'] = "G := SymmetricGroup("+self.name[1:]+");"
        # ... etc
    # ... more checks for dihedral, alternating, special families, etc. ...
    
    # Or use representations if no special family found
    for rep in ["Perm", "PC", "GLZ", "GLFp", "GLZN", "GLZq", "GLFq"]:
        if rep in self.representations:
            code_rep = "permutation" if rep == "Perm" else "presentation" if rep == "PC" else rep
            for lang in code[code_rep]:
                if lang not in code['code_description']:
                    code['code_description'][lang] = code[code_rep][lang]
    
    return code
```

**Key insight:** This method:
1. Loads YAML templates with `{placeholder}` syntax
2. Extracts group representation data from `self.representations`
3. Creates `data` dict with computed values
4. Uses `.format(**data)` to fill in all placeholders
5. Creates special `code_description` entry with best representation

**Properties exposed to templates:**
- `prompt`: Language names
- `show`: Empty dict for show_commands_box
- `code_description`: Top snippet
- `presentation`, `permutation`, `GLZ`, `GLFp`, etc.: Implementation options
- Each has: `comment`, and code for each language

### Step 3: Pass to Template via Helper Methods

File: `lmfdb/groups/abstract/web_groups.py` (lines 2839-2848)

```python
def create_snippet(self, item):
    """Create code snippet for display in table"""
    col_span_val = '"6"'
    snippet = CodeSnippet(self.code_snippets(), item,
                          pre=f"<tr> <td colspan={col_span_val}>",
                          post="</td></tr>")
    return snippet.place_code()

def create_lie_type_snippet(self, item):
    """Create code snippet for Lie type representations"""
    snippet = CodeSnippet(self.code_snippets(), item)
    return snippet.place_code()
```

These methods:
- Call `self.code_snippets()` to get the dict
- Wrap with HTML `<tr>...` if needed
- Call `CodeSnippet.place_code()` to render

### Step 4: Template Uses Snippets

File: `lmfdb/groups/abstract/templates/abstract-show-group.html` (lines 26, 33-42)

```html
<p>
{{ place_code('code_description', is_top_snippet=True) }}
</p>

<h2>Group information</h2>
<table>
    <tr><td>Order:</td><td>{{ info.pos_int_and_factor(gp.order)|safe }}</td> 
        <td>{{ place_code('order') }}</td> 
    </tr>
    <tr><td>Exponent:</td><td>{{ info.pos_int_and_factor(gp.exponent)|safe }}</td> 
        <td>{{ place_code('exponent') }}</td>
    </tr>
    <tr><td>Automorphism group:</td><td>{{gp.aut_group_knowl()|safe}}</td>
        <td>{{ place_code('automorphism_group') }}</td> 
    </tr>
</table>
```

**What happens:**
- `place_code('code_description', is_top_snippet=True)`: Shows best way to construct group
- `place_code('order')`, `place_code('exponent')`, etc.: Show how to compute properties

---

## 4. HOW codeinit AND codeorder ARE EXPOSED

These properties come from the YAML structure and are accessible in templates.

### In code.yaml Structure:

```yaml
prompt:          # Required: language codes → display names
  magma: 'magma'
  sage: 'sage'

comment:         # Optional: shown when code is exported
  magma: Define the group

codeinit:        # Optional: initialization code (e.g., load packages)
  magma: SetPrintLevel(~magma_output_file, 0); // suppress output

codeorder:       # Optional: order of code sections when exporting
  - group_definition
  - generators
  - properties
```

### In Python:

```python
code = yaml.load(open("code.yaml"))
# code['prompt'] → {'magma': 'magma', 'sage': 'sage'}
# code['comment'] → {'magma': 'Define the group', ...}
# code['codeinit'] → {'magma': 'SetPrintLevel(...)'}
# code['codeorder'] → ['group_definition', 'generators', ...]
```

### In Templates via CodeSnippet:

```python
class CodeSnippet:
    def __init__(self, code, item=None):
        self.code = code  # Full dict from YAML
        self.item = item  # Which section to display
        
        if 'prompt' in code:
            self.langs = sorted(code['prompt'])  # Extract available languages
```

The `CodeSnippet` object has access to:
- `self.code['prompt']`
- `self.code['comment']`
- `self.code['codeinit']` (if it exists)
- `self.code['codeorder']` (if it exists)
- `self.code[item]` (the specific code block)

---

## 5. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│ YAML Definition (code.yaml)                                 │
│ ─────────────────────────────────────────────────────────────│
│ prompt:                          # Language display names    │
│   magma: 'magma'               # Maps to 'magma:' in HTML  │
│ curve:                          # Code block identifier      │
│   comment: Define the curve     # Shown in exports          │
│   magma: R<x> := ...{placeholder}...                       │
│ order:                                                       │
│   magma: Order(G);                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Python (e.g., get_code(), code_snippets())                  │
│ ─────────────────────────────────────────────────────────────│
│ 1. Load YAML → {'prompt': {...}, 'curve': {...}, ...}      │
│ 2. Extract data: rdata = self.representations[...]          │
│ 3. Build data dict: {'pccode': 123, 'deg': 5, ...}         │
│ 4. Format templates: code[prop][lang].format(**data)        │
│ 5. Return: {                                                 │
│     'prompt': {'magma': 'magma'},                           │
│     'curve': {'magma': 'R<x> := ...; C := Hyperelliptic(...)'}
│     'order': {'magma': 'Order(G);'}                         │
│   }                                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Template (e.g., g2c_curve.html)                             │
│ ─────────────────────────────────────────────────────────────│
│ <p>{{ place_code('curve', is_top_snippet=True) }}</p>       │
│                                                              │
│ {% macro place_code(item) %}                                │
│   {{ CodeSnippet(code, item).place_code() }}                │
│ {% endmacro %}                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ CodeSnippet Class (place_code.py)                           │
│ ─────────────────────────────────────────────────────────────│
│ class CodeSnippet:                                           │
│   def __init__(self, code, item):                           │
│     self.code = code            # Dict from above           │
│     self.item = item            # 'curve' or 'order'        │
│     self.langs = code['prompt'].keys()  # ['magma']        │
│                                                              │
│   def place_code(self):                                      │
│     for L in self.code[self.item]:  # Iterate languages     │
│       lines = self.code[self.item][L].split('\n')           │
│       prompt = self.code['prompt'][L]  # 'magma'            │
│       # Build HTML with copy button, language switching     │
│       return Markup(html_str)                               │
│                                                              │
│   def show_commands_box(self):                              │
│     # Creates links for each language: magma / sage / pari  │
│     return Markup(box_html)                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Browser HTML Rendering                                     │
│ ─────────────────────────────────────────────────────────────│
│ <div class="magma nodisplay codebox">                       │
│   <span class="prompt">magma:</span>                        │
│   <span class="code">R<x> := PolynomialRing(Rationals())    │
│   fh := [1,2,3];                                            │
│   f := R![a : a in fh[1]];                                  │
│   C := HyperellipticCurve(f);                               │
│   </span>                                                    │
│   <span class="raw-tset-copy-btn">📋</span>                │
│ </div>                                                       │
│                                                              │
│ <div>Show commands: <a>Magma</a> / <a>SageMath</a></div>   │
│ [JavaScript toggles visibility of code blocks]              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. KEY PATTERNS IN THE CODEBASE

### Pattern 1: Static YAML (Genus 2 Curves)
- Load YAML once
- Simple string substitution for placeholders
- Pass dict directly to template

### Pattern 2: Dynamic Templates (Groups)
- Load YAML as templates
- Extract multiple representations from object
- Use `.format(**data)` to fill placeholders
- Create special combined entries like `code_description`

### Pattern 3: Table Wrapping (Groups)
```python
# Wrap code in table cells
CodeSnippet(code, item, pre="<tr><td>", post="</td></tr>")
```

### Pattern 4: Language Options
- `show_commands_box()`: Creates links to toggle between languages
- Each language hidden by default (`nodisplay` class)
- JavaScript shows the selected language class

### Pattern 5: Comment Strings
```python
# Each language has a comment style
comments = {'magma': '//', 'sage': '#', 'gap': '#', 'pari': '\\\\'}

# When exporting code (download functionality):
code += "\n" + comments[lang] + " " + code[key]['comment'] + "\n"
code += code[key][lang]
```

---

## 7. COMPLETE END-TO-END EXAMPLE: Genus 2 Conductor Code

### YAML Definition
```yaml
cond:
  comment: Conductor
  magma: Conductor(LSeries(C));
```

### Object Method
```python
class WebG2C:
    def get_code(self):
        self._code = yaml.load(...)  # Load code.yaml
        # No formatting needed for 'cond' (no placeholders)
        return self._code
```

### Template Call
```html
<td>{{place_code('cond')}}</td>
```

### Macro Expansion
```html
{% macro place_code(item, is_top_snippet=False) %}
  {{ CodeSnippet(code, item).place_code(is_top_snippet=is_top_snippet) }}
{% endmacro %}

<!-- Becomes: -->
{{ CodeSnippet(code, 'cond').place_code(is_top_snippet=False) }}
```

### CodeSnippet Processing
```python
CodeSnippet.place_code():
  code = {
    'prompt': {'magma': 'magma', 'sage': 'sage', 'pari': 'gp'},
    'cond': {
      'comment': 'Conductor',
      'magma': 'Conductor(LSeries(C));',
      'sage': '...',  # if defined
      'pari': '...'   # if defined
    }
  }
  
  item = 'cond'
  # For each language in code['cond']:
  for L in code['cond']:  # L = 'comment', 'magma', 'sage', 'pari'
      if isinstance(code['cond'][L], str):
          lines = [code['cond'][L]]  # Just 'Conductor(LSeries(C));'
          # Skip 'comment', it's not a language
          if L in code['prompt']:  # Check if it's a real language
              # Build HTML...
```

### Resulting HTML
```html
<div class="magma nodisplay codebox">
    <span class="prompt">magma:</span>
    <span class="code">Conductor(LSeries(C));</span>
    <span class="raw-tset-copy-btn"><img alt="Copy"></span>
</div>
<div class="sage nodisplay codebox">
    ...
</div>
<div class="pari nodisplay codebox">
    ...
</div>

<div>Show commands: <a onclick="show_code('magma',...">Magma</a> / 
                    <a onclick="show_code('sage',...">SageMath</a> /
                    <a onclick="show_code('pari',...">Pari/GP</a></div>
```

---

## 8. FILES TO UNDERSTAND

| File | Purpose |
|------|---------|
| `lmfdb/utils/place_code.py` | `CodeSnippet` class - core rendering |
| `lmfdb/app.py` (line 133) | Makes `CodeSnippet` available to all templates via context processor |
| `lmfdb/templates/homepage.html` (lines 1-6) | Base `place_code()` macro definition |
| `*/code.yaml` | YAML templates for code snippets (in each module) |
| `*/web_*.py` | `get_code()` or `code_snippets()` methods that load YAML |
| `*/main.py` | Routes that pass code dict to templates |
| `*/templates/*.html` | Use `place_code()` macro to display |

---

## 9. SUMMARY

**The key insight:** Code snippets flow from YAML files through Python object methods to templates, where a Jinja2 macro calls the `CodeSnippet` class to render interactive HTML with language switching.

1. **YAML stores templates** with placeholders and language variations
2. **Python extracts data and formats** templates with actual values
3. **Templates call `place_code()` macro** with the code dict and item name
4. **`CodeSnippet` class renders** as HTML with copy button and language toggle
5. **`codeinit` and `codeorder`** are optional YAML fields accessible as dict keys for custom code export logic
