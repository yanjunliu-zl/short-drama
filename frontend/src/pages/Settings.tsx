import React, { useState, useEffect } from 'react';
import { Card, Typography, Input, Button, Space, message, Tag } from 'antd';
import {
  KeyOutlined,
  SaveOutlined,
  SettingOutlined,
  ApiOutlined,
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const STORAGE_KEY = 'system_api_keys';

interface ApiKeys {
  llmKey: string;
  seedreamKey: string;
  seedanceKey: string;
}

const loadKeys = (): ApiKeys => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { llmKey: '', seedreamKey: '', seedanceKey: '' };
};

const saveKeys = (keys: ApiKeys) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
};

const Settings: React.FC = () => {
  const [keys, setKeys] = useState<ApiKeys>(loadKeys);
  const [showLl, setShowLl] = useState(false);
  const [showSr, setShowSr] = useState(false);
  const [showSd, setShowSd] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setKeys(loadKeys());
  }, []);

  const handleSave = () => {
    saveKeys(keys);
    setSaved(true);
    message.success('API 密钥已保存');
    setTimeout(() => setSaved(false), 2000);
  };

  const updateKey = (field: keyof ApiKeys, value: string) => {
    setKeys(prev => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const maskKey = (key: string) => {
    if (!key) return '未设置';
    if (key.length <= 8) return '••••••••';
    return key.slice(0, 4) + '••••••••' + key.slice(-4);
  };

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '40px 24px' }}>
      <Title level={3}>
        <SettingOutlined style={{ marginRight: 8 }} />
        系统设置
      </Title>
      <Paragraph type="secondary" style={{ marginBottom: 32 }}>
        配置 AI 服务的 API 密钥。密钥仅保存在本地浏览器，不会上传到服务器。
      </Paragraph>

      {/* LLM Key */}
      <Card
        title={
          <Space>
            <ApiOutlined />
            <span>LLM API Key</span>
            <Tag color="blue">DeepSeek / OpenAI</Tag>
          </Space>
        }
        style={{ marginBottom: 20 }}
      >
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          用于剧本生成、角色提取、实体分析等 AI 文本服务。支持 DeepSeek、OpenAI 兼容接口。
        </Paragraph>
        <Space.Compact style={{ width: '100%' }}>
          <Input.Password
            prefix={<KeyOutlined />}
            value={keys.llmKey}
            onChange={e => updateKey('llmKey', e.target.value)}
            placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
            visibilityToggle={{ visible: showLl, onVisibleChange: setShowLl }}
          />
        </Space.Compact>
        {keys.llmKey && (
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
            当前: {maskKey(keys.llmKey)}
          </Text>
        )}
      </Card>

      {/* Seedream Key */}
      <Card
        title={
          <Space>
            <ApiOutlined />
            <span>Seedream API Key</span>
            <Tag color="purple">图像生成</Tag>
          </Space>
        }
        style={{ marginBottom: 20 }}
      >
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          用于 AI 图像生成服务（Seedream 4.5）。生成角色设定图、场景预览图、分镜首帧等。
        </Paragraph>
        <Space.Compact style={{ width: '100%' }}>
          <Input.Password
            prefix={<KeyOutlined />}
            value={keys.seedreamKey}
            onChange={e => updateKey('seedreamKey', e.target.value)}
            placeholder="请输入 Seedream API Key"
            visibilityToggle={{ visible: showSr, onVisibleChange: setShowSr }}
          />
        </Space.Compact>
        {keys.seedreamKey && (
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
            当前: {maskKey(keys.seedreamKey)}
          </Text>
        )}
      </Card>

      {/* Seedance Key */}
      <Card
        title={
          <Space>
            <ApiOutlined />
            <span>Seedance API Key</span>
            <Tag color="orange">视频生成</Tag>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          用于 AI 视频生成服务（Seedance 2.0）。将分镜图像转为动态视频片段。
        </Paragraph>
        <Space.Compact style={{ width: '100%' }}>
          <Input.Password
            prefix={<KeyOutlined />}
            value={keys.seedanceKey}
            onChange={e => updateKey('seedanceKey', e.target.value)}
            placeholder="请输入 Seedance API Key"
            visibilityToggle={{ visible: showSd, onVisibleChange: setShowSd }}
          />
        </Space.Compact>
        {keys.seedanceKey && (
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
            当前: {maskKey(keys.seedanceKey)}
          </Text>
        )}
      </Card>

      <Button
        type="primary"
        size="large"
        icon={<SaveOutlined />}
        onClick={handleSave}
        disabled={saved}
        block
      >
        {saved ? '已保存' : '保存设置'}
      </Button>
    </div>
  );
};

export default Settings;
