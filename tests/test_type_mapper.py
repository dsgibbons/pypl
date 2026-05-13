from pypl import cpp
from pypl.analyzer.model import ClassKind
from pypl.analyzer.type_mapper import TypeMapper
from pypl.warnings import WarningCollector


class _Foo:
    pass


def _mk(kind_map: dict[str, ClassKind] | None = None) -> tuple[TypeMapper, WarningCollector]:
    w = WarningCollector()
    return TypeMapper(
        warnings=w,
        kind_map=kind_map or {},
        current_module="tests.test_type_mapper",
        variant_qnames={},
    ), w


def test_primitives():
    m, _ = _mk()
    assert m.map(int, where="x").cpp_text == "int"
    assert m.map(float, where="x").cpp_text == "double"
    assert m.map(str, where="x").cpp_text == "std::string"
    assert m.map(bool, where="x").cpp_text == "bool"


def test_optional_value():
    m, _ = _mk()
    assert m.map(int | None, where="x").cpp_text == "std::optional<int>"


def test_shared_ptr():
    m, _ = _mk()
    ref = m.map(cpp.Shared[_Foo], where="x")
    assert "std::shared_ptr<" in ref.cpp_text
    assert ref.cpp_text.endswith("__Foo>") or "_Foo" in ref.cpp_text


def test_unique_ptr_optional_keeps_pointer():
    m, _ = _mk()
    # cpp.Unique[Foo] | None stays as unique_ptr (already nullable).
    ref = m.map(cpp.Unique[_Foo] | None, where="x")
    assert "std::unique_ptr<" in ref.cpp_text
    assert "std::optional<" not in ref.cpp_text


def test_ref_optional_warns():
    m, w = _mk()
    m.map(cpp.Ref[_Foo] | None, where="x")
    codes = [warn.code for warn in w.warnings]
    assert "nullable-reference" in codes


def test_unmarked_class_warns_and_defaults_to_raw():
    m, w = _mk(kind_map={f"{_Foo.__module__}.{_Foo.__qualname__}": ClassKind.CLASS})
    ref = m.map(_Foo, where="x")
    assert ref.cpp_text.endswith("*")
    codes = [warn.code for warn in w.warnings]
    assert "unmarked-class-ref" in codes


def test_value_class_no_warn():
    # Struct kind -> value type, no warning.
    m, w = _mk(kind_map={f"{_Foo.__module__}.{_Foo.__qualname__}": ClassKind.STRUCT})
    ref = m.map(_Foo, where="x")
    assert not ref.cpp_text.endswith("*")
    codes = [warn.code for warn in w.warnings]
    assert "unmarked-class-ref" not in codes


def test_list_to_vector():
    m, _ = _mk()
    assert m.map(list[int], where="x").cpp_text == "std::vector<int>"


def test_dict_to_unordered_map():
    m, _ = _mk()
    assert m.map(dict[str, int], where="x").cpp_text == "std::unordered_map<std::string, int>"


def test_omap_override():
    m, _ = _mk()
    assert m.map(cpp.OMap[str, int], where="x").cpp_text == "std::map<std::string, int>"


def test_vec_alias():
    m, _ = _mk()
    assert m.map(cpp.Vec[int], where="x").cpp_text == "std::vector<int>"


def test_frozenset_const_unordered_set():
    m, _ = _mk()
    assert m.map(frozenset[str], where="x").cpp_text == "const std::unordered_set<std::string>"
