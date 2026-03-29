import copy

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.context_strategy import MessageContextStrategyDefaults
from server.application.domain.model.session import Session
from server.application.port.outbound.llm_port_factory import ILlmPortFactory
from server.application.port.outbound.model_billing_factory import IModelBillingFactory
from server.application.port.outbound.session_repository import ISessionRepository


class CreateSessionUseCase:
    def __init__(
        self,
        repository: ISessionRepository,
        llm_factory: ILlmPortFactory,
        model_billing_factory: IModelBillingFactory,
        default_completion_config: CompletionConfig,
        strategy_defaults: dict[str, MessageContextStrategyDefaults],
        default_strategy_type: str,
    ) -> None:
        self._repository = repository
        self._llm_factory = llm_factory
        self._model_billing_factory = model_billing_factory
        self._default_completion_config = default_completion_config
        self._strategy_defaults = strategy_defaults
        self._default_strategy_type = default_strategy_type

    async def execute(self, session_id: str) -> Session:
        completion_config = copy.copy(self._default_completion_config)

        if self._default_strategy_type not in self._strategy_defaults:
            raise ValueError(f"Unknown default strategy type: {self._default_strategy_type!r}")
        defaults = self._strategy_defaults[self._default_strategy_type]
        strategy_completion_config = copy.copy(defaults.completion_config)

        llm = self._llm_factory.create(session_id, completion_config)
        strategy_llm = self._llm_factory.create(session_id, strategy_completion_config)

        billing = self._model_billing_factory.create(completion_config.provider, completion_config.model)
        strategy_billing = self._model_billing_factory.create(
            strategy_completion_config.provider, strategy_completion_config.model
        )

        session = await Session.create(
            llm=llm,
            id=session_id,
            completion_config=completion_config,
            billing=billing,
            strategy_type=self._default_strategy_type,
            strategy_metadata=defaults.metadata,
            strategy_llm=strategy_llm,
            strategy_completion_config=strategy_completion_config,
            strategy_billing=strategy_billing,
        )
        self._repository.create_session(session)
        return session
