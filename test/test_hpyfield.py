"""
NOTE: these tests are also meant to be run as PyPy "applevel" tests.

This means that global imports will NOT be visible inside the test
functions. In particular, you have to "import pytest" inside the test in order
to be able to use e.g. pytest.raises (which on PyPy will be implemented by a
"fake pytest module")
"""
from .support import HPyTest, DefaultExtensionTemplate

class PairTemplate(DefaultExtensionTemplate):

    def DEFINE_PairObject(self):
        return """
            typedef struct {
                HPyField a;
                HPyField b;
            } PairObject;
        
            HPyType_HELPERS(PairObject);
        """

    def DEFINE_Pair_new(self):
        return """
            HPyDef_SLOT(Pair_new, Pair_new_impl, HPy_tp_new)
            static HPy Pair_new_impl(HPyContext *ctx, HPy cls, HPy *args,
                                      HPy_ssize_t nargs, HPy kw)
            {
                HPy a;
                HPy b;
                if (!HPyArg_Parse(ctx, NULL, args, nargs, "OO", &a, &b))
                    return HPy_NULL;
                PairObject *pair;
                HPy h_obj = HPy_New(ctx, cls, &pair);
                HPyField_Store(ctx, &pair->a, a);
                HPyField_Store(ctx, &pair->b, b);
                return h_obj;
            }
        """

    def DEFINE_Pair_traverse(self):
        return """
            HPyDef_SLOT(Pair_traverse, Pair_traverse_impl, HPy_tp_traverse)
            static int Pair_traverse_impl(HPyContext *ctx, HPy self,
                                          HPyFunc_visitproc visit, void *arg)
            {
                PairObject *p = PairObject_AsStruct(ctx, self);
                HPy_VISIT(&p->a);
                HPy_VISIT(&p->b);
                return 0;
            }
        """

    def DEFINE_Pair_get_ab(self):
        return """
            HPyDef_METH(Pair_get_a, "get_a", Pair_get_a_impl, HPyFunc_NOARGS)
            static HPy Pair_get_a_impl(HPyContext *ctx, HPy self)
            {
                PairObject *pair = PairObject_AsStruct(ctx, self);
                return HPyField_Load(ctx, pair->a);
            }

            HPyDef_METH(Pair_get_b, "get_b", Pair_get_b_impl, HPyFunc_NOARGS)
            static HPy Pair_get_b_impl(HPyContext *ctx, HPy self)
            {
                PairObject *pair = PairObject_AsStruct(ctx, self);
                return HPyField_Load(ctx, pair->b);
            }
        """

    pair_type_flags = 'HPy_TPFLAGS_DEFAULT | HPy_TPFLAGS_HAVE_GC'
    def PAIR_TYPE_FLAGS(self, flags):
        self.pair_type_flags = flags

    def EXPORT_PAIR_TYPE(self, *defines):
        defines += ('NULL',)
        defines = ', '.join(defines)
        self.EXPORT_TYPE('"Pair"', "Pair_spec")
        return """
            static HPyDef *Pair_defines[] = { %s };
            static HPyType_Spec Pair_spec = {
                .name = "mytest.Pair",
                .basicsize = sizeof(PairObject),
                .flags = %s,
                .defines = Pair_defines
            };
        """ % (defines, self.pair_type_flags)

class TestHPyField(HPyTest):

    ExtensionTemplate = PairTemplate

    def test_store_load(self):
        import sys
        mod = self.make_module("""
            @DEFINE_PairObject
            @DEFINE_Pair_new
            @DEFINE_Pair_get_ab

            @PAIR_TYPE_FLAGS(HPy_TPFLAGS_DEFAULT)
            @EXPORT_PAIR_TYPE(&Pair_new, &Pair_get_a, &Pair_get_b)
            @INIT
        """)
        p = mod.Pair("hello", "world")
        assert p.get_a() == 'hello'
        assert p.get_b() == 'world'
        #
        # check the refcnt
        if self.supports_refcounts():
            a = object()
            a_refcnt = sys.getrefcount(a)
            p2 = mod.Pair(a, None)
            assert sys.getrefcount(a) == a_refcnt + 1
            assert p2.get_a() is a
            assert sys.getrefcount(a) == a_refcnt + 1

    def test_store_overwrite(self):
        import sys
        mod = self.make_module("""
            #include <assert.h>
            @DEFINE_PairObject
            @DEFINE_Pair_new
            @DEFINE_Pair_get_ab

            HPyDef_METH(Pair_overwrite_a, "overwrite_a", Pair_overwrite_a_impl, HPyFunc_NOARGS)
            static HPy Pair_overwrite_a_impl(HPyContext *ctx, HPy self)
            {
                PairObject *pair = PairObject_AsStruct(ctx, self);
                assert(!HPy_IsNull(pair->a));
                HPyField_Store(ctx, &pair->a, ctx->h_None);
                return HPy_Dup(ctx, ctx->h_None);
            }

            @PAIR_TYPE_FLAGS(HPy_TPFLAGS_DEFAULT)
            @EXPORT_PAIR_TYPE(&Pair_new, &Pair_get_a, &Pair_get_b, &Pair_overwrite_a)
            @INIT
        """)
        p = mod.Pair("hello", "world")
        assert p.get_a() == 'hello'
        assert p.get_b() == 'world'
        p.overwrite_a()
        assert p.get_a() is None
        #
        # check the refcnt
        if self.supports_refcounts():
            a = object()
            a_refcnt = sys.getrefcount(a)
            p2 = mod.Pair(a, None)
            assert sys.getrefcount(a) == a_refcnt + 1
            assert p2.get_a() is a
            p2.overwrite_a()
            assert sys.getrefcount(a) == a_refcnt


    def test_clear(self):
        import sys
        mod = self.make_module("""
            #include <assert.h>
            @DEFINE_PairObject
            @DEFINE_Pair_new
            @DEFINE_Pair_get_ab

            HPyDef_METH(Pair_clear_a, "clear_a", Pair_clear_a_impl, HPyFunc_NOARGS)
            static HPy Pair_clear_a_impl(HPyContext *ctx, HPy self)
            {
                PairObject *pair = PairObject_AsStruct(ctx, self);
                assert(!HPy_IsNull(pair->a));
                HPyField_Clear(ctx, &pair->a);
                pair->a = HPyField_Store(ctx, ctx->h_None);
                return HPy_Dup(ctx, ctx->h_None);
            }

            @PAIR_TYPE_FLAGS(HPy_TPFLAGS_DEFAULT)
            @EXPORT_PAIR_TYPE(&Pair_new, &Pair_get_a, &Pair_get_b, &Pair_clear_a)
            @INIT
        """)
        p = mod.Pair("hello", "world")
        assert p.get_a() == 'hello'
        assert p.get_b() == 'world'
        p.clear_a()
        assert p.get_a() is None
        #
        # check the refcnt
        if self.supports_refcounts():
            a = object()
            a_refcnt = sys.getrefcount(a)
            p2 = mod.Pair(a, None)
            assert sys.getrefcount(a) == a_refcnt + 1
            assert p2.get_a() is a
            p2.clear_a()
            assert sys.getrefcount(a) == a_refcnt

    def test_gc_track(self):
        # Test that we correctly call PyObject_GC_Track on CPython. The
        # easiest way is to check whether the object is in
        # gc.get_objects(). This test might need to be tweaked and/or disabled
        # for alternative implementations: after all, it's mostly a test about
        # the CPython-specific implementation.
        import gc
        mod = self.make_module("""
            @DEFINE_PairObject
            @DEFINE_Pair_new
            @DEFINE_Pair_traverse

            @EXPORT_PAIR_TYPE(&Pair_new, &Pair_traverse)
            @INIT
        """)
        p = mod.Pair("hello", "world")
        assert p in gc.get_objects()
        assert gc.is_tracked(p)

    def test_gc_track_no_gc_flag(self):
        # Same code as test_gc_track, but without HPy_TPFLAGS_HAVE_GC. On
        # CPython, the object is NOT tracked. Again, this is probably a
        # CPython-specific test.
        import gc
        mod = self.make_module("""
            @DEFINE_PairObject
            @DEFINE_Pair_new
            @DEFINE_Pair_traverse

            @PAIR_TYPE_FLAGS(HPy_TPFLAGS_DEFAULT)
            @EXPORT_PAIR_TYPE(&Pair_new, &Pair_traverse)
            @INIT
        """)
        p = mod.Pair("hello", "world")
        assert p not in gc.get_objects()
        assert not gc.is_tracked(p)

    def test_tp_traverse(self):
        import gc
        mod = self.make_module("""
            @DEFINE_PairObject
            @DEFINE_Pair_new
            @DEFINE_Pair_traverse

            @EXPORT_PAIR_TYPE(&Pair_new, &Pair_traverse)
            @INIT
        """)
        p = mod.Pair("hello", "world")
        referents = gc.get_referents(p)
        referents.sort()
        assert referents == ['hello', 'world']

    def test_tp_traverse_sanity_check(self):
        import pytest
        with pytest.raises(ValueError):
            self.make_module("""
                @DEFINE_PairObject
                @DEFINE_Pair_new

                // here we are defining a type with HPy_TPFLAGS_HAVE_GC but
                // without providing a tp_traverse
                @EXPORT_PAIR_TYPE(&Pair_new)
                @INIT
            """)
