"""Models base compartilhados para o projeto Lacrei Saúde."""

from django.db import models, router
from django.db.models.deletion import Collector


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet que suporta soft-delete em lote."""

    def delete(self):
        """Soft-delete em lote com verificação de integridade relacional."""
        del_query = self._chain()
        del_query._for_write = True
        del_query.query.select_for_update = False
        del_query.query.select_related = False
        del_query.query.clear_ordering(force=True)

        collector = Collector(using=del_query.db, origin=self)
        collector.collect(del_query)
        return self.update(ativo=False)

    def soft_delete(self):
        """Soft-delete em lote direto sem checagem de Collector."""
        return self.update(ativo=False)

    def hard_delete(self):
        """Delete físico real — usar apenas em migrações ou manutenção."""
        return super().delete()

    def ativos(self):
        """Retorna apenas registros ativos."""
        return self.filter(ativo=True)

    def inativos(self):
        """Retorna apenas registros inativos."""
        return self.filter(ativo=False)


class SoftDeleteManager(models.Manager):
    """Manager padrão que expõe apenas registros ativos."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(ativo=True)

    def get(self, *args, **kwargs):
        """Permite obter uma instância por PK/campos mesmo se inativa."""
        return SoftDeleteQuerySet(self.model, using=self._db).get(*args, **kwargs)


class AllObjectsManager(models.Manager):
    """Manager que expõe TODOS os registros (incluindo inativos)."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Model abstrato com suporte a soft-delete seguro a nível de ORM.

    Uso:
        class MeuModel(SoftDeleteModel):
            nome = models.CharField(max_length=100)

    Managers:
        - MeuModel.objects → apenas registros ativos (padrão seguro)
        - MeuModel.all_objects → todos os registros (admin/auditoria)

    Métodos:
        - instance.delete() → soft-delete (ativo=False)
        - instance.hard_delete() → remoção física
        - instance.restore() → reativação (ativo=True)
    """

    ativo = models.BooleanField("Ativo", default=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft-delete com verificação de integridade referencial via Collector."""
        using = using or router.db_for_write(self.__class__, instance=self)
        collector = Collector(using=using, origin=self)
        collector.collect([self], keep_parents=keep_parents)
        self.ativo = False
        self.save(update_fields=["ativo"])
        return 1, {self._meta.label: 1}

    def soft_delete(self):
        """Soft-delete direto: marca o registro como inativo sem verificação relacional."""
        self.ativo = False
        self.save(update_fields=["ativo"])

    def hard_delete(self, using=None, keep_parents=False):
        """Delete físico real — usar com cautela."""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """Restaura um registro inativado."""
        self.ativo = True
        self.save(update_fields=["ativo"])
