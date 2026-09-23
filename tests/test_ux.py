import copy
import json
from types import SimpleNamespace

import pytest

from testwins.config import load, validate
from testwins.ux import assess, contract, catalog
from testwins.ux_review import SubllmClient, validate_repairs, evidence_bundle


def config():
    cfg = load()
    cfg['ux']['strategy'] = 'dashboard'
    cfg['journeys'] = [{'id': 'filter', 'path': '/', 'steps': [
        {'id': 'choose', 'action': 'click', 'selector': '#choose', 'allow_mutation': True,
         'expect': {'kind': 'text', 'selector': '#result', 'value': 'Ready'}, 'ux': {}}
    ]}]
    return cfg


def observation(**kwargs):
    return {'input_observed': True, 'response_ms': 90, 'feedback_ms': 20, 'announced': True,
            'focus_matches': True, 'visual_changed': True, 'motion_target_observed': True,
            'motion_ms': 100, 'infinite_motion': False, **kwargs}


def test_strategy_defaults_and_operator_budget_override():
    cfg = config(); step = cfg['journeys'][0]['steps'][0]
    cfg['ux']['budgets'] = {'response_ms': 4000}; step['ux']['feedback_ms'] = 123
    validate(cfg)
    spec = contract(cfg, step)
    assert spec['response_ms'] == 4000 and spec['feedback_ms'] == 123
    assert set(catalog()['strategies']) == {'dashboard', 'form', 'commerce', 'content'}


@pytest.mark.parametrize('change', [
    lambda c: c['ux'].update(strategy='magic'),
    lambda c: c['ux'].update(habit='magic'),
    lambda c: c['ux']['budgets'].update(response_ms=True),
    lambda c: c['ux']['budgets'].update(response_ms=9000),
    lambda c: c['ux'].update(unknown=True),
    lambda c: c['journeys'][0]['steps'][0]['ux'].update(motion='#box'),
    lambda c: c['journeys'][0]['steps'][0]['ux'].update(announce=True),
    lambda c: c['journeys'][0]['steps'][0]['ux'].update(feedback={'kind':'changed'}),
    lambda c: c['ux'].update(habit='keyboard'),
    lambda c: c['ux'].update(strategy=None),
    lambda c: c.update(journeys=[]),
])
def test_invalid_ux_config_fails_before_browser(change):
    cfg = config(); change(cfg)
    with pytest.raises(ValueError): validate(cfg)


def test_ux_contract_checks_every_layer_without_repetition_requirement():
    cfg = config(); spec = contract(cfg, cfg['journeys'][0]['steps'][0])
    spec.update(feedback={'kind':'visible','selector':'#status'}, announce=True,
                focus='#result', visual_change='#choose', motion='#panel')
    result = assess(spec, observation(response_ms=4000, feedback_ms=900, announced=False,
                                     focus_matches=False, visual_changed=False, infinite_motion=True), True)
    assert result['status'] == 'failed'
    assert set(x['layer'] for x in result['violations']) == set(catalog()['layers'])
    assert result['unobserved_layers'] == []
    assert assess(spec, observation(input_observed=False), True)['status'] == 'incomplete'
    assert assess(spec, observation(motion_target_observed=False), True)['status'] == 'incomplete'


def test_unobserved_layers_remain_explicit():
    cfg = config(); spec = contract(cfg, cfg['journeys'][0]['steps'][0])
    result = assess(spec, observation(), True)
    assert result['status'] == 'passed'
    assert result['assessed_layers'] == ['functionality']
    assert set(result['unobserved_layers']) == {'graphics','information','feedback','motion'}


def test_required_ux_cannot_be_removed_from_a_passed_report():
    from testwins.gate import evaluate, plan_checks
    cfg = config(); cells = ['chromium-desktop']; plan = plan_checks(cfg,cfg['journeys'],cells)
    report = {'schema':'testwins.report/v1','cell_plan':cells,'check_plan':plan,
              'checks':[dict(c,status='passed') for c in plan], 'coverage':{'state':'complete'},
              'cells':[{'id':cells[0],'complete':True}], 'summary':{}}
    assert evaluate(report)['status'] == 'incomplete'
    for c in report['checks']: c['ux'] = {'status':'failed'}
    assert evaluate(report)['status'] == 'failed'
    for c in report['checks']: c['ux'] = {'status':'passed'}
    assert evaluate(report)['status'] == 'passed'


def sdk(transport='openai-compatible', endpoint='https://example.com/v1', content='{"repairs":[]}'):
    class FakeSDK:
        calls = []
        def configured_routes(self, *args, **kwargs):
            return [SimpleNamespace(transport=transport, api_base=endpoint)]
        def complete(self, *args, **kwargs):
            self.calls.append((args,kwargs))
            return SimpleNamespace(content=content,provider='sample',model='model-a',attempts=[1],usage={'total_tokens':12,'secret':'no'})
    return FakeSDK()


def test_subllm_uses_public_completion_and_reports_actual_model():
    backend = sdk(); values = {'SUBLLM_PROVIDER_ORDER':'openrouter','LLM_ALLOW_REMOTE':'1'}
    result, meta = SubllmClient(values,sdk=backend).call([{'role':'user','content':'bounded evidence'}])
    assert result == {'repairs':[]}
    assert meta['provider'] == 'sample' and meta['model'] == 'model-a'
    assert meta['usage'] == {'total_tokens':12}
    args, kwargs = backend.calls[0]
    assert args[:2] == ('repair-agent','repair-plan') and kwargs['timeout_seconds'] == 60
    assert kwargs['environ'] == values


@pytest.mark.parametrize('transport', ['cursor-sdk','codex-cli','claude-cli'])
def test_review_cannot_select_local_agent_execution(transport):
    backend = sdk(transport=transport)
    with pytest.raises(ValueError,match='data-only'):
        SubllmClient({'SUBLLM_PROVIDER_ORDER':'cursor','LLM_ALLOW_REMOTE':'1'},sdk=backend).call([])
    assert not backend.calls


def test_remote_consent_and_explicit_route_required_before_call():
    backend = sdk()
    for values in ({}, {'SUBLLM_PROVIDER_ORDER':'openrouter'}):
        with pytest.raises(ValueError): SubllmClient(values,sdk=backend).call([])
    assert not backend.calls
    backend = sdk(endpoint='http://127.0.0.1:8080')
    SubllmClient({'SUBLLM_PROVIDER_ORDER':'ollama'},sdk=backend).call([])
    assert len(backend.calls) == 1


def test_provider_errors_never_expose_prompt_or_credentials():
    backend = sdk()
    def fail(*args,**kwargs): raise RuntimeError('KEY-secret and private prompt')
    backend.complete = fail
    with pytest.raises(RuntimeError) as exc:
        SubllmClient({'SUBLLM_PROVIDER_ORDER':'openrouter','LLM_ALLOW_REMOTE':'1'},sdk=backend).call([])
    assert 'KEY-secret' not in str(exc.value) and 'private prompt' not in str(exc.value)


@pytest.mark.parametrize('mutation', [
    lambda r: r['repairs'][0].update(evidence_id='invented'),
    lambda r: r['repairs'][0].update(command='delete all'),
    lambda r: r['repairs'].append(copy.deepcopy(r['repairs'][0])),
    lambda r: r.update(repairs=[]),
    lambda r: r['repairs'][0].update(diagnosis=''),
])
def test_model_output_is_closed_and_bound_to_evidence(mutation):
    value = {'repairs':[{'evidence_id':'one','diagnosis':'Likely state bug','change':'Show pending state','verification':'Repeat declared action'}]}
    mutation(value)
    with pytest.raises(ValueError): validate_repairs(value,[{'evidence_id':'one'}])
