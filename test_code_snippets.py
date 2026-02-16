#!/usr/bin/env python
"""
Simple test to validate code snippet implementations
"""
import sys
import traceback

def test_imports():
    """Test that all imports work"""
    try:
        print("Testing imports...")
        from lmfdb.utils import CodeSnippet
        print("✓ CodeSnippet imported successfully")
        
        from lmfdb.characters.web_character import WebDBDirichletCharacter
        print("✓ WebDBDirichletCharacter imported successfully")
        
        from lmfdb.characters.main import dirchar_code, sorted_code_names
        print("✓ dirchar_code imported successfully")
        
        print("\nAll imports successful!")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_code_yaml():
    """Test that code.yaml is valid"""
    try:
        print("\nTesting code.yaml parsing...")
        import yaml
        import os
        
        yaml_path = "/workspaces/lmfdb/lmfdb/characters/code.yaml"
        with open(yaml_path) as f:
            code = yaml.load(f, Loader=yaml.FullLoader)
        
        print(f"✓ code.yaml loaded successfully")
        
        # Check required keys
        required_keys = ['prompt', 'frontmatter', 'init', 'modulus', 'cond', 'order']
        for key in required_keys:
            if key not in code:
                print(f"✗ Missing required key: {key}")
                return False
        
        print(f"✓ All required keys present: {', '.join(required_keys)}")
        
        # Check languages
        langs = code['prompt'].keys()
        print(f"✓ Languages defined: {', '.join(langs)}")
        
        return True
    except Exception as e:
        print(f"✗ code.yaml test failed: {e}")
        traceback.print_exc()
        return False

def test_code_snippet_access():
    """Test that CodeSnippet class works"""
    try:
        print("\nTesting CodeSnippet class...")
        from lmfdb.utils import CodeSnippet
        
        test_code = {
            'prompt': {'sage': 'sage', 'pari': 'gp'},
            'show': {'sage': '', 'pari': ''},
            'frontmatter': {
                'all': 'Code for {label}'
            },
            'init': {
                'comment': 'Initialize',
                'sage': 'x = 1',
                'pari': 'x = 1'
            }
        }
        
        cs = CodeSnippet(test_code, item='init')
        print("✓ CodeSnippet created successfully")
        
        # Test place_code
        html = cs.place_code()
        if 'x = 1' in str(html):
            print("✓ place_code() works and contains code")
        else:
            print("✗ place_code() didn't produce expected output")
            return False
        
        return True
    except Exception as e:
        print(f"✗ CodeSnippet test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    results = [
        test_imports(),
        test_code_yaml(),
        test_code_snippet_access(),
    ]
    
    print("\n" + "="*50)
    if all(results):
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
