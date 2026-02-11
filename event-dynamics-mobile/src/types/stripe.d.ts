// Type declarations for @stripe/stripe-react-native
declare module '@stripe/stripe-react-native' {
  import React from 'react';
  import { ViewStyle } from 'react-native';

  interface StripeProviderProps {
    publishableKey: string;
    merchantIdentifier?: string;
    urlScheme?: string;
    children: React.ReactNode;
  }

  export function StripeProvider(props: StripeProviderProps): React.JSX.Element;

  export namespace CardFieldInput {
    interface Details {
      complete: boolean;
      brand?: string;
      last4?: string;
      expiryMonth?: number;
      expiryYear?: number;
      postalCode?: string;
      validNumber?: string;
      validCVC?: string;
      validExpiryDate?: string;
    }
  }

  interface CardFieldProps {
    postalCodeEnabled?: boolean;
    placeholders?: {
      number?: string;
      expiration?: string;
      cvc?: string;
      postalCode?: string;
    };
    cardStyle?: {
      backgroundColor?: string;
      textColor?: string;
      borderColor?: string;
      borderWidth?: number;
      borderRadius?: number;
      fontSize?: number;
      placeholderColor?: string;
      cursorColor?: string;
      textErrorColor?: string;
    };
    style?: ViewStyle;
    onCardChange?: (cardDetails: CardFieldInput.Details) => void;
    onFocus?: (focusedField: string | null) => void;
  }

  export function CardField(props: CardFieldProps): React.JSX.Element;

  interface PaymentIntentResult {
    paymentIntent?: {
      id: string;
      status: 'Succeeded' | 'RequiresAction' | 'RequiresConfirmation' | 'Canceled' | 'Processing' | 'RequiresPaymentMethod';
      amount: number;
      currency: string;
    };
    error?: {
      code: string;
      message: string;
      localizedMessage?: string;
      declineCode?: string;
      type?: string;
    };
  }

  interface ConfirmPaymentParams {
    paymentMethodType: 'Card' | 'Ideal' | 'Bancontact' | 'Giropay' | 'Eps' | 'Sofort' | 'SepaDebit';
    paymentMethodData?: {
      billingDetails?: {
        email?: string;
        name?: string;
        phone?: string;
        address?: {
          city?: string;
          country?: string;
          line1?: string;
          line2?: string;
          postalCode?: string;
          state?: string;
        };
      };
    };
  }

  interface UseStripeReturn {
    confirmPayment: (clientSecret: string, params: ConfirmPaymentParams) => Promise<PaymentIntentResult>;
    retrievePaymentIntent: (clientSecret: string) => Promise<PaymentIntentResult>;
    isPlatformPaySupported: (params?: { googlePay?: { testEnv?: boolean } }) => Promise<boolean>;
    confirmPlatformPayPayment: (clientSecret: string, params: { googlePay?: { testEnv?: boolean; currencyCode: string; merchantCountryCode: string }; applePay?: { cartItems: Array<{ label: string; amount: string; paymentType?: string }>; merchantCountryCode: string; currencyCode: string } }) => Promise<PaymentIntentResult>;
  }

  export function useStripe(): UseStripeReturn;
  export function usePlatformPay(): { isPlatformPaySupported: boolean; confirmPlatformPayPayment: UseStripeReturn['confirmPlatformPayPayment'] };
}
