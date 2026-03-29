from server.application.domain.model.context_strategy import MessageContextStrategyFactory
from server.application.domain.model.llm_stats_decorator import LlmStatsDecorator
from server.application.domain.model.session import Session
from server.application.domain.model.usage_stats import SessionUsageStats
from server.application.port.outbound.llm_port_factory import ILlmPortFactory
from server.application.port.outbound.model_billing_factory import IModelBillingFactory
from server.application.port.outbound.session_repository import ISessionRepository


class GetSessionUseCase:
    def __init__(
        self,
        repository: ISessionRepository,
        llm_factory: ILlmPortFactory,
        model_billing_factory: IModelBillingFactory,
    ) -> None:
        self._repository = repository
        self._llm_factory = llm_factory
        self._model_billing_factory = model_billing_factory

    async def execute(self, session_id: str) -> Session:
        state = self._repository.get_session(session_id)

        llm = self._llm_factory.create(session_id, state.completion_config)
        strategy_llm = self._llm_factory.create(session_id, state.strategy_completion_config)
        billing = self._model_billing_factory.create(state.completion_config.provider, state.completion_config.model)
        strategy_billing = self._model_billing_factory.create(
            state.strategy_completion_config.provider,
            state.strategy_completion_config.model,
        )

        usage_stats = SessionUsageStats(data=state.statistics)
        strategy_llm_stats = LlmStatsDecorator(llm=strategy_llm, usage_stats=usage_stats, billing=strategy_billing)

        strategy = MessageContextStrategyFactory.build(
            state.strategy_type,
            state.strategy_metadata,
            state.strategy_records,
            strategy_llm_stats,
            state.strategy_completion_config,
        )

        return Session(
            llm=llm,
            id=state.id,
            created_at=state.created_at,
            completion_config=state.completion_config,
            billing=billing,
            usage_stats=usage_stats,
            message_context_strategy=strategy,
        )
