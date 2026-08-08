"""Notificações de task.

O serviço original lia a própria configuração no construtor (`smtp.gmail.com`,
usuário e senha hardcoded), instanciava `smtplib.SMTP` sem timeout dentro do
método, e — o detalhe que fecha o quadro — nunca era instanciado por ninguém.

Agora recebe mailer e configuração por construtor, tem timeout explícito, e vem
desligado por padrão: enviar email de dentro de um handler HTTP é decisão que
precisa ser tomada conscientemente, não herdada.
"""
import smtplib
from email.message import EmailMessage


class NullMailer:
    """Mailer usado quando as notificações estão desligadas."""

    def send(self, destinatario, assunto, corpo):
        return False


class SmtpMailer:
    def __init__(self, settings, logger):
        self._settings = settings
        self._logger = logger

    def send(self, destinatario, assunto, corpo):
        mensagem = EmailMessage()
        mensagem["From"] = self._settings.smtp_user
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.set_content(corpo)

        try:
            with smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=self._settings.smtp_timeout,
            ) as servidor:
                servidor.starttls()
                servidor.login(self._settings.smtp_user, self._settings.smtp_password)
                servidor.send_message(mensagem)
            return True
        except OSError:
            # Falha de entrega não pode derrubar a operação de negócio que a
            # disparou. O erro é registrado com stack completa.
            self._logger.exception("falha ao enviar email")
            return False


class NotificationService:
    def __init__(self, mailer, logger, enabled=False):
        self._mailer = mailer
        self._logger = logger
        self._enabled = enabled

    def task_atribuida(self, task):
        if not task.user:
            return
        self._enviar(
            task.user.email,
            f"Nova task atribuída: {task.title}",
            f"Olá {task.user.name},\n\nA task '{task.title}' foi atribuída a você."
            f"\n\nPrioridade: {task.priority}\nStatus: {task.status}",
            evento="task_atribuida",
            task_id=task.id,
        )

    def task_atrasada(self, task):
        if not task.user:
            return
        self._enviar(
            task.user.email,
            f"Task atrasada: {task.title}",
            f"Olá {task.user.name},\n\nA task '{task.title}' está atrasada!"
            f"\n\nData limite: {task.due_date}",
            evento="task_atrasada",
            task_id=task.id,
        )

    def _enviar(self, destinatario, assunto, corpo, evento, task_id):
        if not self._enabled:
            self._logger.debug(
                "notificação suprimida", extra={"evento": evento, "task_id": task_id}
            )
            return
        self._mailer.send(destinatario, assunto, corpo)
        self._logger.info("notificação enviada", extra={"evento": evento, "task_id": task_id})
