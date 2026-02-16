# Testing Guide: Dirichlet Character Code Snippets

## Quick Start Testing

### Test 1: Verify Files Were Modified Correctly

```bash
cd /workspaces/lmfdb

# Check that code.yaml exists and is valid YAML
python3 -c "import yaml; yaml.safe_load(open('lmfdb/characters/code.yaml'))"

# Verify main.py compiles
python3 -m py_compile lmfdb/characters/main.py

# Verify web_character.py compiles
python3 -m py_compile lmfdb/characters/web_character.py
```

### Test 2: Verify YAML Structure

```bash
python3 << 'EOF'
import yaml

with open('lmfdb/characters/code.yaml') as f:
    code = yaml.safe_load(f)

# Check required top-level keys
required = ['prompt', 'frontmatter', 'init', 'modulus', 'cond', 'order']
for key in required:
    assert key in code, f"Missing required key: {key}"

# Check languages
langs = code['prompt'].keys()
print(f"Languages: {list(langs)}")

# Check some code snippets have content
for lang in langs:
    assert 'sage' in code['init'] or 'pari' in code['init'], "init missing code"

print("✓ YAML structure is valid")
EOF
```

### Test 3: Run Character Tests

```bash
cd /workspaces/lmfdb

# Configure environment first
source /usr/share/miniconda/etc/profile.d/conda.sh 2>/dev/null || true
conda activate lmfdb 2>/dev/null || true

# Run character-specific tests
sage -python -m pytest lmfdb/characters/test_characters.py -v
```

### Test 4: Verify Routes Exist

```bash
python3 << 'EOF'
import ast
import re

with open('lmfdb/characters/main.py') as f:
    content = f.read()

# Check for route decorators
routes = re.findall(r"@characters_page\.route\('([^']+)'\)", content)
print("Found routes:")
for route in routes:
    print(f"  - {route}")

# Check for specific download routes we added
assert any('download' in r for r in routes), "No download routes found"
print("\n✓ Download routes exist")
EOF
```

### Test 5: Test Code Snippet Loading

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspaces/lmfdb')

from lmfdb.utils import CodeSnippet
from lmfdb.characters.web_character import WebDBDirichletCharacter

# Create a test code dict similar to what code_snippets() returns
test_code = {
    'prompt': {'sage': 'sage', 'pari': 'gp', 'magma': 'magma'},
    'show': {'sage': '', 'pari': '', 'magma': ''},
    'init': {
        'comment': 'Initialize character',
        'sage': 'chi = 1',
        'pari': 'chi = 1', 
        'magma': 'chi := 1;'
    },
    'frontmatter': {
        'all': '{lang} code for {label}'
    }
}

# Test CodeSnippet class
cs = CodeSnippet(test_code, item='init')
html = cs.place_code()
print("✓ CodeSnippet renders successfully")
print(f"  HTML length: {len(str(html))} chars")

# Test export_code
exported = cs.export_code('test.1', 'sage', ['init'])
print(f"✓ export_code works")
print(f"  Exported code length: {len(exported)} chars")
EOF
```

## Manual Testing (Requires Running Server)

### Prerequisites
```bash
cd /workspaces/lmfdb

# Setup environment
source /usr/share/miniconda/etc/profile.d/conda.sh 2>/dev/null || true
conda activate lmfdb

# Install dependencies if needed
sage -pip install -q -r requirements.txt
```

### Test Pages

1. **Individual Character Page**
   - URL: `http://localhost:37777/Character/Dirichlet/5/2`
   - Expected: "Downloads" sidebar with three code download links:
     - Sage commands
     - Pari/GP commands  
     - Magma commands
   - Also should show code snippets inline next to property tables

2. **Character Orbit Page**
   - URL: `http://localhost:37777/Character/Dirichlet/5/a`
   - Expected: Same download links as above, but for the orbit
   - Code should work with the entire orbit, not just one character

3. **Download Links**
   - Click "Sage commands" → Should download text file with Sage code
   - Click "Pari/GP commands" → Should download text file with Pari code
   - Click "Magma commands" → Should download text file with Magma code

### Verify Downloaded Code Format

The downloaded file should contain:
```
# Sage code for working with Dirichlet character 5.2

# Define the Dirichlet character:
from sage.modular.dirichlet import DirichletCharacter
H = DirichletGroup(5)
chi = H[2]

# Modulus:
chi.modulus()

# Conductor:
chi.conductor()

... (more code snippets)
```

## Troubleshooting

### Issue: "No module named 'CodeSnippet'"
**Solution**: Check that lmfdb/utils/__init__.py exports CodeSnippet (it should)

### Issue: "Invalid Dirichlet character label"
**Solution**: The format must be `modulus.number` for characters or `modulus.orbit_label` for orbits

### Issue: YAML format errors
**Solution**: Check code.yaml for proper indentation (2 spaces) and valid YAML syntax

### Issue: Code snippets showing None in template
**Solution**: This means __getattr__ isn't finding the code snippet. Check:
1. Does the snippet name in YAML match what's being requested?
2. Did code_snippets() method run without exceptions?

## Validation Checklist

- [ ] Files compile without syntax errors
- [ ] YAML parses correctly
- [ ] CodeSnippet class instantiates
- [ ] Routes are defined for downloads
- [ ] Character page shows download sidebar
- [ ] Orbit page shows download sidebar
- [ ] Download links are clickable and return files
- [ ] Downloaded Sage code is valid Python/Sage
- [ ] Downloaded Pari code is valid Pari/GP syntax
- [ ] Downloaded Magma code is valid Magma syntax

