import React, { useState } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Slider,
  Button,
  Space,
  Typography,
  message,
  Row,
  Col,
  InputNumber,
  Alert
} from 'antd';
import { scriptService } from '@/services/scriptService';
import { ScriptGenre, ScriptStyle, type ScriptGenerationRequest } from '@/types/script';

const { Title, Text } = Typography;
const { TextArea } = Input;

const Home: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [generatedScriptId, setGeneratedScriptId] = useState<string | null>(null);

  // 剧本类型选项
  const genreOptions = Object.values(ScriptGenre).map(genre => ({
    value: genre,
    label: genre.charAt(0).toUpperCase() + genre.slice(1).replace('-', ' ')
  }));

  // 剧本风格选项
  const styleOptions = Object.values(ScriptStyle).map(style => ({
    value: style,
    label: style.charAt(0).toUpperCase() + style.slice(1)
  }));

  // 处理表单提交
  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      const requestData: ScriptGenerationRequest = {
        title: values.title,
        description: values.description,
        genre: values.genre,
        target_duration_minutes: values.target_duration_minutes,
        character_count: values.character_count,
        style: values.style,
        theme: values.theme,
        additional_requirements: values.additional_requirements
      };

      const response = await scriptService.generateScript(requestData);

      if (response.code === 200) {
        message.success('剧本生成任务已提交！');
        setGeneratedScriptId(response.data!.task_id);
        form.resetFields();
      } else {
        message.error(response.message || '生成失败，请重试');
      }
    } catch (error) {
      console.error('生成剧本失败:', error);
      message.error('生成失败，请检查网络连接');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2} style={{ marginBottom: '24px' }}>短剧生成平台</Title>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card
            title="生成新剧本"
            bordered={false}
            style={{ marginBottom: '24px' }}
          >
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSubmit}
              initialValues={{
                target_duration_minutes: 10,
                character_count: 4,
                genre: ScriptGenre.Romance
              }}
            >
              <Form.Item
                name="title"
                label="剧本标题"
                rules={[{ required: true, message: '请输入剧本标题' }]}
              >
                <Input placeholder="例如：咖啡馆的邂逅" maxLength={100} />
              </Form.Item>

              <Form.Item
                name="description"
                label="剧本简介"
              >
                <TextArea
                  placeholder="简单描述剧本的主要情节"
                  rows={3}
                  maxLength={500}
                  showCount
                />
              </Form.Item>

              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="genre"
                    label="剧本类型"
                    rules={[{ required: true, message: '请选择剧本类型' }]}
                  >
                    <Select
                      placeholder="选择剧本类型"
                      options={genreOptions}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="style"
                    label="写作风格"
                  >
                    <Select
                      placeholder="选择写作风格（可选）"
                      options={styleOptions}
                      allowClear
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="target_duration_minutes"
                    label="目标时长（分钟）"
                    rules={[{ required: true, message: '请输入目标时长' }]}
                  >
                    <Slider
                      min={1}
                      max={60}
                      marks={{
                        1: '1分钟',
                        10: '10分钟',
                        30: '30分钟',
                        60: '60分钟'
                      }}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="character_count"
                    label="角色数量"
                    rules={[{ required: true, message: '请输入角色数量' }]}
                  >
                    <InputNumber
                      min={1}
                      max={20}
                      style={{ width: '100%' }}
                      placeholder="1-20个角色"
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="theme"
                label="主题关键词"
              >
                <Input placeholder="例如：爱情、友情、成长、复仇" maxLength={100} />
              </Form.Item>

              <Form.Item
                name="additional_requirements"
                label="附加要求"
              >
                <TextArea
                  placeholder="其他特殊要求，如：需要包含反转结局、需要适合儿童观看等"
                  rows={3}
                  maxLength={1000}
                  showCount
                />
              </Form.Item>

              <Form.Item>
                <Space size="large">
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={loading}
                    size="large"
                  >
                    {loading ? '生成中...' : '开始生成剧本'}
                  </Button>
                  <Button
                    onClick={() => form.resetFields()}
                    size="large"
                  >
                    重置
                  </Button>
                </Space>
              </Form.Item>
            </Form>

            {generatedScriptId && (
              <Alert
                message="剧本生成任务已提交"
                description={
                  <Text>
                    任务ID：<Text code>{generatedScriptId}</Text>。
                    剧本生成需要一些时间，请稍后在剧本列表中查看结果。
                  </Text>
                }
                type="success"
                showIcon
                closable
                onClose={() => setGeneratedScriptId(null)}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="如何使用" bordered={false} style={{ marginBottom: '24px' }}>
            <Space direction="vertical" size="middle">
              <div>
                <Title level={5}>1. 填写基本信息</Title>
                <Text type="secondary">输入剧本标题、简介和选择类型</Text>
              </div>
              <div>
                <Title level={5}>2. 设置参数</Title>
                <Text type="secondary">调整时长、角色数量和风格偏好</Text>
              </div>
              <div>
                <Title level={5}>3. 提交生成</Title>
                <Text type="secondary">AI将根据您的需求创作剧本</Text>
              </div>
              <div>
                <Title level={5}>4. 查看结果</Title>
                <Text type="secondary">生成完成后可在剧本列表中查看和编辑</Text>
              </div>
            </Space>
          </Card>

          <Card title="平台特性" bordered={false}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div>
                <Text strong>AI智能创作</Text>
                <Text type="secondary" style={{ display: 'block' }}>基于先进AI模型生成高质量剧本</Text>
              </div>
              <div>
                <Text strong>多类型支持</Text>
                <Text type="secondary" style={{ display: 'block' }}>爱情、喜剧、悬疑等多种剧本类型</Text>
              </div>
              <div>
                <Text strong>快速生成</Text>
                <Text type="secondary" style={{ display: 'block' }}>几分钟内完成剧本创作</Text>
              </div>
              <div>
                <Text strong>灵活编辑</Text>
                <Text type="secondary" style={{ display: 'block' }}>支持生成后编辑和优化</Text>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Home;