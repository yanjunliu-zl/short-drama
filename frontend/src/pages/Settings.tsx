import React, { useState } from 'react';
import {
  Card,
  Form,
  Switch,
  Input,
  Button,
  Select,
  Divider,
  Typography,
  Space,
  message,
  Row,
  Col,
  Slider,
  InputNumber,
} from 'antd';
import {
  SettingOutlined,
  SaveOutlined,
  ReloadOutlined,
  ApiOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  // 模拟加载设置
  const loadSettings = () => {
    const mockSettings = {
      notifications: true,
      autoSave: true,
      saveInterval: 10,
      theme: 'light',
      language: 'zh-CN',
      apiEndpoint: 'https://api.example.com',
      securityLevel: 'medium',
      watermark: true,
      watermarkText: 'TopSeeker',
      maxUploadSize: 100,
    };
    form.setFieldsValue(mockSettings);
  };

  React.useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async (values: any) => {
    setLoading(true);
    try {
      // 模拟 API 调用
      await new Promise((resolve) => setTimeout(resolve, 800));
      console.log('保存设置:', values);
      message.success('设置保存成功');
    } catch (error) {
      message.error('保存失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    form.resetFields();
    loadSettings();
    message.info('设置已重置');
  };

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <SettingOutlined style={{ marginRight: 12 }} />
          全局设定
        </Title>
        <Text type="secondary">配置系统参数、用户偏好及安全选项</Text>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          notifications: true,
          autoSave: true,
          saveInterval: 10,
          theme: 'light',
          language: 'zh-CN',
          apiEndpoint: 'https://api.example.com',
          securityLevel: 'medium',
          watermark: true,
          watermarkText: 'TopSeeker',
          maxUploadSize: 100,
        }}
      >
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={12}>
            <Card title="常规设置" size="small">
              <Form.Item
                label="启用通知"
                name="notifications"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                label="自动保存"
                name="autoSave"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                label="保存间隔（分钟）"
                name="saveInterval"
                dependencies={['autoSave']}
              >
                {({ getFieldValue }) =>
                  getFieldValue('autoSave') ? (
                    <Slider
                      min={1}
                      max={60}
                      marks={{ 1: '1', 30: '30', 60: '60' }}
                    />
                  ) : (
                    <Text type="secondary">自动保存已禁用</Text>
                  )
                }
              </Form.Item>
              <Form.Item label="界面主题" name="theme">
                <Select>
                  <Option value="light">浅色</Option>
                  <Option value="dark">深色</Option>
                  <Option value="auto">跟随系统</Option>
                </Select>
              </Form.Item>
              <Form.Item label="语言" name="language">
                <Select>
                  <Option value="zh-CN">简体中文</Option>
                  <Option value="zh-TW">繁体中文</Option>
                  <Option value="en-US">English</Option>
                </Select>
              </Form.Item>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card title="安全与隐私" size="small">
              <Form.Item label="安全级别" name="securityLevel">
                <Select>
                  <Option value="low">低</Option>
                  <Option value="medium">中（推荐）</Option>
                  <Option value="high">高</Option>
                </Select>
              </Form.Item>
              <Form.Item
                label="启用水印"
                name="watermark"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                label="水印文本"
                name="watermarkText"
                dependencies={['watermark']}
              >
                {({ getFieldValue }) =>
                  getFieldValue('watermark') ? (
                    <Input placeholder="输入水印文本" />
                  ) : (
                    <Text type="secondary">水印已禁用</Text>
                  )
                }
              </Form.Item>
              <Form.Item label="最大上传大小（MB）" name="maxUploadSize">
                <InputNumber min={1} max={1024} style={{ width: '100%' }} />
              </Form.Item>
            </Card>
          </Col>
        </Row>

        <Card title="API 与集成" size="small" style={{ marginTop: 24 }}>
          <Form.Item
            label="API 端点"
            name="apiEndpoint"
            rules={[{ required: true, message: '请输入 API 端点' }]}
          >
            <Input prefix={<ApiOutlined />} placeholder="https://api.example.com" />
          </Form.Item>
          <Form.Item label="云存储同步" name="cloudSync" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="第三方集成" name="thirdPartyIntegrations">
            <Select mode="multiple" placeholder="选择要启用的集成">
              <Option value="github">GitHub</Option>
              <Option value="gitlab">GitLab</Option>
              <Option value="dropbox">Dropbox</Option>
              <Option value="googleDrive">Google Drive</Option>
              <Option value="onedrive">OneDrive</Option>
            </Select>
          </Form.Item>
        </Card>

        <Divider />

        <div style={{ textAlign: 'right', marginTop: 24 }}>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleReset}
              disabled={loading}
            >
              重置
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              htmlType="submit"
              loading={loading}
            >
              保存设置
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  );
};

export default Settings;